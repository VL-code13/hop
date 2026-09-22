"""
Глобальные фикстуры pytest для проекта Hop & Barley.

Покрывает: пользователей, категории, товары, корзину, заказы, отзывы.
Все фабрики создают минимально валидные объекты.
"""

from decimal import Decimal
from itertools import count

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory

from orders.cart import Cart
from orders.models import Order, OrderItem
from products.models import Category, Product
from reviews.models import Review

User = get_user_model()


# ──────────────────────── Инфраструктура ────────────────────────


@pytest.fixture(autouse=True)
def _disable_ssl_redirect(settings):
    """Отключает HTTPS-редирект для тестового клиента.

    В config.settings.ci стоит SECURE_SSL_REDIRECT=True (проверка прод-конфига),
    но тестовый клиент ходит по HTTP → SecurityMiddleware отдаёт 301.
    Здесь отключаем только для тестов.
    """
    settings.SECURE_SSL_REDIRECT = False


@pytest.fixture
def request_factory():
    """RequestFactory для имитации запросов без прогонки через middleware."""
    return RequestFactory()


# ──────────────────────── Пользователи ────────────────────────


@pytest.fixture
def user_factory(db):
    """Фабрика пользователей. Возвращает функцию-создатель."""
    counter = count(1)

    def make(**kwargs):
        idx = next(counter)
        defaults = {
            'username': f'testuser_{idx}',
            'email': f'testusermail_{idx}@domain.com',
            'password': 'testpass123',
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    return make


@pytest.fixture
def user(db, user_factory):
    """Основной тестовый пользователь."""
    return user_factory(username='testuser', email='testusermail@domain.com')


@pytest.fixture
def other_user(db, user_factory):
    """Второй пользователь — для проверки прав доступа."""
    return user_factory(username='otheruser', email='otheruser@domain.com')


@pytest.fixture
def admin_user(db, user_factory):
    """Суперпользователь для тестов админки."""
    return user_factory(
        username='admin',
        email='admin@domain.com',
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def request_with_user(request_factory, user):
    """Запрос с сессией и авторизованным пользователем.

    RequestFactory не прогоняет middleware, поэтому SessionMiddleware
    вызываем вручную — иначе у request не будет .session, и Cart упадёт.
    """
    request = request_factory.post('/')
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    request.user = user
    return request


# ──────────────────────── Каталог ────────────────────────


@pytest.fixture
def category_factory(db):
    """Фабрика категорий."""
    counter = count(1)

    def make(**kwargs):
        idx = next(counter)
        defaults = {
            'name': f'Категория {idx}',
            'slug': f'category-{idx}',
        }
        defaults.update(kwargs)
        return Category.objects.create(**defaults)

    return make


@pytest.fixture
def category(db, category_factory):
    """Категория по умолчанию."""
    return category_factory(name='Светлое пиво', slug='light-beer')


@pytest.fixture
def child_category(db, category_factory, category):
    """Дочерняя категория — для тестов иерархии."""
    return category_factory(name='Pale Ale', slug='pale-ale', parent=category)


@pytest.fixture
def product_factory(db, category_factory):
    """Фабрика товаров. Категория создаётся лениво, если не передана явно."""
    counter = count(1)

    def make(**kwargs):
        idx = next(counter)
        defaults = {
            'name': f'Товар {idx}',
            'slug': f'product-{idx}',
            'description': f'Описание товара {idx}',
            'price': Decimal('500.00'),
            'category': category_factory(),
            'is_active': True,
            'stock': 10,
        }
        defaults.update(kwargs)
        return Product.objects.create(**defaults)

    return make


@pytest.fixture
def product(db, product_factory):
    """Товар по умолчанию — активный, 10 шт. на складе, 500 ₽."""
    return product_factory(name='Pale Ale', slug='pale-ale')


@pytest.fixture
def out_of_stock_product(db, product_factory):
    """Товар с нулевым остатком."""
    return product_factory(name='Sold Out Stout', slug='sold-out-stout', stock=0)


@pytest.fixture
def inactive_product(db, product_factory):
    """Скрытый с витрины товар."""
    return product_factory(name='Hidden Lager', slug='hidden-lager', is_active=False)


# ──────────────────────── Корзина ────────────────────────


@pytest.fixture
def cart(request_with_user):
    """Сессионная корзина, привязанная к запросу с пользователем."""
    return Cart(request_with_user)


@pytest.fixture
def cart_with_product(cart, product):
    """Корзина с одним товаром (2 шт.)."""
    cart.add(product=product, quantity=2)
    return cart


# ──────────────────────── Заказы ────────────────────────


@pytest.fixture
def order_factory(db, user, product_factory):
    """Фабрика заказов. Создаёт Order + OrderItem автоматически."""

    def make(**kwargs):
        prod = kwargs.pop('product', product_factory())
        quantity = kwargs.pop('quantity', 1)
        status = kwargs.pop('status', Order.Status.PENDING)
        payment_method = kwargs.pop('payment_method', Order.PaymentMethod.CARD)

        order = Order.objects.create(
            user=kwargs.pop('user', user),
            status=status,
            payment_method=payment_method,
            total_price=Decimal('0.00'),
            shipping_address='Москва, ул. Тестовая, д. 1',
            **kwargs,
        )
        OrderItem.objects.create(
            order=order,
            product=prod,
            price=prod.price,
            quantity=quantity,
        )
        order.total_price = order.get_total_cost()
        order.save(update_fields=['total_price'])
        return order

    return make


@pytest.fixture
def order(db, order_factory):
    """Заказ по умолчанию — PENDING, 1 товар, 1 шт."""
    return order_factory()


@pytest.fixture
def paid_order(db, order_factory):
    """Оплаченный заказ — для тестов отзывов и доставки."""
    return order_factory(status=Order.Status.PAID)


@pytest.fixture
def delivered_order(db, order_factory):
    """Доставленный заказ."""
    return order_factory(status=Order.Status.DELIVERED)


# ──────────────────────── Отзывы ────────────────────────


@pytest.fixture
def review_factory(db, paid_order):
    """
    Фабрика отзывов.

    По умолчанию привязывает отзыв к товару из paid_order
    и к пользователю этого заказа — так соблюдается бизнес-правило
    «отзыв только после покупки».
    """
    counter = count(1)

    def make(**kwargs):
        idx = next(counter)
        order = kwargs.pop('order', paid_order)
        product = kwargs.pop('product', order.items.first().product)
        review_user = kwargs.pop('user', order.user)

        defaults = {
            'product': product,
            'user': review_user,
            'rating': 5,
            'comment': f'Отличный товар {idx}!',
        }
        defaults.update(kwargs)
        return Review.objects.create(**defaults)

    return make


@pytest.fixture
def review(db, review_factory):
    """Отзыв по умолчанию — 5 звёзд."""
    return review_factory()
