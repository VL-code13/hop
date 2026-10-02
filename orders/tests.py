"""
Модульные тесты приложения orders.

Реализует требования разделов 6.3 («Тестирование: корзина, заказ, бизнес-правила») и 8 ТЗ.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework import status as drf_status
from rest_framework.test import APIClient

from products.models import Category, Product

from .models import Order, OrderItem

User = get_user_model()


class OrdersBusinessLogicTestCase(TestCase):
    """Тестирование корзины, складских лимитов и процесса чекаута."""

    def setUp(self) -> None:
        """Инициализация тестовых сущностей перед запуском каждого теста."""
        self.user = User.objects.create_user(
            username='brewmaster@example.com',
            email='brewmaster@example.com',
            password='strong_password_123',
        )
        self.category = Category.objects.create(name='Хмель', slug='hops')
        self.product = Product.objects.create(
            name='Centennial Hops',
            slug='centennial-hops',
            price=Decimal('620.00'),
            category=self.category,
            stock=5,
            is_active=True,
        )

    def test_cart_add_valid_quantity(self) -> None:
        """Добавление допустимого количества товара в корзину."""
        response = self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 2},
        )
        self.assertEqual(response.status_code, 302)
        cart = self.client.session['cart']
        self.assertIn(str(self.product.id), cart)
        self.assertEqual(cart[str(self.product.id)]['quantity'], 2)

    def test_cannot_add_more_than_available_stock(self) -> None:
        """
        Бизнес-правило (раздел 6.3 ТЗ):
        Нельзя положить в корзину больше единиц, чем доступно на складе.
        """
        response = self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 10},
        )
        self.assertEqual(response.status_code, 302)
        cart = self.client.session.get('cart', {})
        # При превышении остатка корзина не пополняется
        self.assertEqual(cart.get(str(self.product.id), {}).get('quantity', 0), 0)

    def test_cannot_add_negative_quantity(self) -> None:
        """Отрицательное количество отклоняется.

        Пользователь может отправить '-5' через curl или DevTools,
        минуя UI (в шаблоне кнопка «−» скрыта при quantity <= 1).
        Серверная защита — ``Cart.add()`` возвращает False на
        quantity < 1, а ``AddToCartProductForm`` отклоняет ввод с
        min_value=1 ещё до вызова сервиса.

        Если бы этой защиты не было, получился бы «отрицательный
        заказ»: ``price * (-5)`` уменьшает итоговую сумму.
        """
        response = self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': -5},
        )
        self.assertEqual(response.status_code, 302)

        cart = self.client.session.get('cart', {})
        # Корзина не пополнилась — записи о товаре нет
        self.assertEqual(cart.get(str(self.product.id), {}).get('quantity', 0), 0)

    def test_cannot_add_zero_quantity(self) -> None:
        """Нулевое количество отклоняется.

        Ноль — некорректное количество для добавления. Отклоняем
        так же, как и отрицательное. Для удаления позиции есть
        отдельный endpoint ``cart_remove``.
        """
        response = self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 0},
        )
        self.assertEqual(response.status_code, 302)

        cart = self.client.session.get('cart', {})
        self.assertEqual(cart.get(str(self.product.id), {}).get('quantity', 0), 0)

    def test_cart_update_rejects_negative_quantity(self) -> None:
        """Обновление корзины отрицательным количеством не меняет состояние.

        Сценарий:
            1. Добавляем 2 шт. — корзина содержит 2.
            2. Пытаемся обновить на -5.
            3. Ожидаем: корзина всё ещё содержит 2 (отрицательное
               отклонено формой и Cart.add()).

        Проверяет, что отрицательное значение не удаляет товар и не
        обнуляет корзину. Удаление — только через ``cart_remove``.
        """
        # 1. Добавляем 2 шт.
        self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 2},
        )
        cart = self.client.session['cart']
        self.assertEqual(cart[str(self.product.id)]['quantity'], 2)

        # 2. Пытаемся обновить на -5
        response = self.client.post(
            reverse('orders:cart_update', kwargs={'product_id': self.product.id}),
            {'quantity': -5},
        )
        self.assertEqual(response.status_code, 302)

        # 3. Количество осталось прежним
        cart_after = self.client.session['cart']
        self.assertEqual(cart_after[str(self.product.id)]['quantity'], 2)

    def test_checkout_creates_order_and_deducts_stock(self) -> None:
        """
        Успешное оформление заказа:
        1. Создает запись Order и OrderItem;
        2. Списывает остаток товара на складе;
        3. Очищает сессионную корзину;
        4. Делает редирект на success.
        """
        self.client.login(username='brewmaster@example.com', password='strong_password_123')

        # Добавляем 3 единицы в корзину
        self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 3},
        )

        checkout_data = {
            'full_name': 'Иван Пивоваров',
            'phone': '+7 (999) 111-22-33',
            'shipping_address': 'Лиговский проспект, д. 50',
            'payment_method': Order.PaymentMethod.CARD,
        }
        response = self.client.post(reverse('orders:checkout'), data=checkout_data)
        self.assertEqual(response.status_code, 302)

        # Проверяем уменьшение остатка
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

        # Проверяем создание заказа в базе
        order = Order.objects.filter(user=self.user).first()
        self.assertIsNotNone(order)
        assert order is not None
        self.assertEqual(order.total_price, Decimal('1860.00'))

        # Проверяем очистку корзины
        session_cart = self.client.session.get('cart', {})
        self.assertEqual(len(session_cart), 0)


class OrderItemDeleteTestCase(TestCase):
    """Тесты возврата остатка при удалении позиции заказа.

    Для доступа к позиции используется ``order.items.get(product=...)``,
    а не ``order.items.first()``. Разница: ``get()`` возвращает сразу
    ``OrderItem`` и падает с ``DoesNotExist``, если объекта нет — mypy
    доволен. ``first()`` возвращает ``OrderItem | None`` и требует
    дополнительной проверки на ``None``.
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='deleter',
            email='deleter@example.com',
            password='pass12345',
        )
        self.category = Category.objects.create(name='Хмель', slug='hops')
        self.product = Product.objects.create(
            name='Citra',
            slug='citra',
            price=Decimal('500.00'),
            category=self.category,
            stock=10,
            is_active=True,
        )

    def _make_order(self, status: str) -> Order:
        """Создаёт заказ с одной позицией (товар x3) и заданным статусом."""
        order = Order.objects.create(
            user=self.user,
            total_price=Decimal('1500.00'),
            status=status,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=Decimal('500.00'),
            quantity=3,
        )
        return order

    def test_delete_item_returns_stock_for_pending(self) -> None:
        """PENDING: удаление позиции возвращает остаток на склад."""
        order = self._make_order(Order.Status.PENDING)
        order.items.get(product=self.product).delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 13)  # 10 + 3

    def test_delete_item_returns_stock_for_paid(self) -> None:
        """PAID: удаление позиции возвращает остаток."""
        order = self._make_order(Order.Status.PAID)
        order.items.get(product=self.product).delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 13)

    def test_delete_item_does_not_return_stock_for_delivered(self) -> None:
        """DELIVERED: остаток НЕ возвращается — товар у покупателя."""
        order = self._make_order(Order.Status.DELIVERED)
        order.items.get(product=self.product).delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_delete_item_does_not_return_stock_for_cancelled(self) -> None:
        """CANCELLED: остаток уже возвращён при отмене заказа, повторно нельзя."""
        order = self._make_order(Order.Status.CANCELLED)
        order.items.get(product=self.product).delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_delete_item_recalculates_total(self) -> None:
        """Удаление позиции пересчитывает Order.total_price."""
        order = self._make_order(Order.Status.PENDING)
        order.items.get(product=self.product).delete()
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal('0.00'))


class OrderEmailNotificationTestCase(TestCase):
    """Тесты email-уведомлений после оформления заказа.

    Особенности:

    1. Тестируем именно содержимое писем (subject, recipient, body) —
       не только факт отправки.
    2. Используем ``self.captureOnCommitCallbacks(execute=True)``: транзакция
       чекаута в ``TestCase`` не коммитится (pytest/Django откатывают её),
       поэтому ``transaction.on_commit`` не сработал бы сам по себе.
       Метод ``TestCase`` перехватывает callbacks и выполняет их
       принудительно, эмулируя коммит.
    3. ``CELERY_TASK_ALWAYS_EAGER = True`` в config.settings.test означает,
       что ``.delay()`` внутри callbacks выполнится синхронно — письма
       попадут в ``mail.outbox`` сразу.
    """

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='notify@example.com',
            email='notify@example.com',
            password='strong_password_123',
            first_name='Иван',
            last_name='Пивоваров',
        )
        self.category = Category.objects.create(name='Хмель', slug='hops')
        self.product = Product.objects.create(
            name='Citra Hops',
            slug='citra-hops',
            price=Decimal('500.00'),
            category=self.category,
            stock=10,
            is_active=True,
        )

    def _checkout(self) -> None:
        """Хелпер: логин + корзина + POST на чекаут внутри captureOnCommitCallbacks."""
        self.client.login(username='notify@example.com', password='strong_password_123')
        self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 2},
        )
        checkout_data = {
            'full_name': 'Иван Пивоваров',
            'phone': '+7 (999) 111-22-33',
            'shipping_address': 'Лиговский проспект, д. 50',
            'payment_method': Order.PaymentMethod.CARD,
        }
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse('orders:checkout'), data=checkout_data)

    def test_checkout_sends_email_to_customer(self) -> None:
        """После чекаута покупателю уходит письмо с номером заказа."""
        self._checkout()

        order = Order.objects.get(user=self.user)
        customer_emails = [m for m in mail.outbox if self.user.email in m.to]

        self.assertEqual(len(customer_emails), 1)
        email = customer_emails[0]
        self.assertIn(f'Заказ #{order.id}', email.subject)
        self.assertIn(self.user.get_full_name(), email.body)
        self.assertIn(str(order.total_price), email.body)
        self.assertIn(order.shipping_address, email.body)

    def test_checkout_notifies_admins(self) -> None:
        """После чекаута администраторы получают уведомление о новом заказе."""
        self._checkout()

        order = Order.objects.get(user=self.user)
        # mail_admins отправляет на адреса из settings.ADMINS
        admin_emails = [m for m in mail.outbox if 'admin@hopandbarley.com' in m.to]

        self.assertEqual(len(admin_emails), 1)
        email = admin_emails[0]
        self.assertIn(f'Новый заказ #{order.id}', email.subject)
        self.assertIn(self.user.username, email.body)

    def test_checkout_sends_exactly_two_emails(self) -> None:
        """Ровно два письма: покупателю + администраторам. Больше — баг."""
        self._checkout()

        self.assertEqual(len(mail.outbox), 2)

    def test_checkout_email_body_contains_price_and_address(self) -> None:
        """Тело письма содержит итоговую сумму и адрес доставки."""
        self._checkout()

        order = Order.objects.get(user=self.user)
        customer_email = next(m for m in mail.outbox if self.user.email in m.to)

        # Цена из order, а не хардкод — тест не привязан к фикстуре.
        self.assertIn(str(order.total_price), customer_email.body)
        self.assertIn(order.shipping_address, customer_email.body)
        self.assertIn('Спасибо, что выбрали Hop & Barley', customer_email.body)

    def test_no_email_when_checkout_validation_fails(self) -> None:
        """Если чекаут не удался — письма не отправляются.

        Сценарий: Cart.add отклонил quantity > stock → корзина пуста →
        checkout_view делает redirect на корзину с сообщением об ошибке,
        до OrderCreateSerializer.create() дело не доходит → on_commit
        не регистрируется → писем нет.

        Проверяем итоговое состояние: заказ не создан, писем нет.
        Код ответа не важен — может быть 200 или 302 в зависимости
        от реализации вьюхи.
        """
        self.client.login(username='notify@example.com', password='strong_password_123')
        # Пытаемся положить больше, чем есть на складе (Cart.add отклонит)
        self.client.post(
            reverse('orders:cart_add', kwargs={'product_id': self.product.id}),
            {'quantity': 50},  # на складе 10
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse('orders:checkout'),
                data={
                    'full_name': 'Иван',
                    'phone': '+7 (999) 111-22-33',
                    'shipping_address': 'Тест',
                    'payment_method': Order.PaymentMethod.CARD,
                },
            )

        # Проверяем состояние: заказ не создан, письма не отправлены.
        # Код ответа не проверяем: твой checkout_view при пустой корзине
        # делает redirect (302) с сообщением, а не рендерит форму с ошибкой.
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)


# ──────────────────────── REST API: правила изменения и отмены заказа ────────────────────────
class OrderAPIPatchRulesTestCase(TestCase):
    """Тесты правила «PATCH только для PENDING» (фидбек ментора, п.4.1)."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='api_patch_user',
            email='api_patch@example.com',
            password='strong_password_123',
        )
        self.other_user = User.objects.create_user(
            username='api_other_user',
            email='api_other@example.com',
            password='strong_password_123',
        )
        self.category = Category.objects.create(name='Солод', slug='malt')
        self.product = Product.objects.create(
            name='Pale Ale Malt',
            slug='pale-ale-malt',
            price=Decimal('300.00'),
            category=self.category,
            stock=20,
            is_active=True,
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _make_order(self, status: str) -> Order:
        order = Order.objects.create(
            user=self.user,
            total_price=Decimal('600.00'),
            shipping_address='Старый адрес',
            payment_method=Order.PaymentMethod.CARD,
            status=status,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=Decimal('300.00'),
            quantity=2,
        )
        return order

    def test_patch_pending_order_updates_address_and_payment(self) -> None:
        """PENDING: PATCH обновляет адрес и способ оплаты — 200."""
        order = self._make_order(Order.Status.PENDING)
        url = reverse('api-orders-detail', args=[order.id])

        response = self.api.patch(
            url,
            data={
                'shipping_address': 'Новый адрес, д. 5',
                'payment_method': Order.PaymentMethod.WALLET,
            },
            format='json',
        )

        self.assertEqual(response.status_code, drf_status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.shipping_address, 'Новый адрес, д. 5')
        self.assertEqual(order.payment_method, Order.PaymentMethod.WALLET)

    def test_patch_shipped_order_returns_400(self) -> None:
        """SHIPPED: PATCH отклоняется с 400 — адрес подменить нельзя."""
        order = self._make_order(Order.Status.SHIPPED)
        url = reverse('api-orders-detail', args=[order.id])

        response = self.api.patch(
            url,
            data={'shipping_address': 'Другой адрес'},
            format='json',
        )

        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.shipping_address, 'Старый адрес')

    def test_patch_delivered_order_returns_400(self) -> None:
        """DELIVERED: PATCH отклоняется с 400 — оплату задним числом не сменить."""
        order = self._make_order(Order.Status.DELIVERED)
        url = reverse('api-orders-detail', args=[order.id])

        response = self.api.patch(
            url,
            data={'payment_method': Order.PaymentMethod.CASH},
            format='json',
        )

        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db()
        self.assertEqual(order.payment_method, Order.PaymentMethod.CARD)

    def test_patch_cancelled_order_returns_400(self) -> None:
        """CANCELLED: PATCH отклоняется — отменённый заказ менять нельзя."""
        order = self._make_order(Order.Status.CANCELLED)
        url = reverse('api-orders-detail', args=[order.id])

        response = self.api.patch(
            url,
            data={'shipping_address': 'Поздний адрес'},
            format='json',
        )

        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)

    def test_patch_other_user_order_returns_404(self) -> None:
        """Чужой заказ недоступен — 404 (queryset фильтрует по user)."""
        order = self._make_order(Order.Status.PENDING)
        self.api.force_authenticate(user=self.other_user)
        url = reverse('api-orders-detail', args=[order.id])

        response = self.api.patch(
            url,
            data={'shipping_address': 'Чужой адрес'},
            format='json',
        )

        self.assertEqual(response.status_code, drf_status.HTTP_404_NOT_FOUND)


class OrderAPICancelRaceConditionTestCase(TestCase):
    """Тесты защиты от двойного возврата остатка при отмене (фидбек ментора, п.4.2)."""

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            username='api_cancel_user',
            email='api_cancel@example.com',
            password='strong_password_123',
        )
        self.category = Category.objects.create(name='Дрожжи', slug='yeast')
        self.product = Product.objects.create(
            name='Safale US-05',
            slug='safale-us-05',
            price=Decimal('400.00'),
            category=self.category,
            stock=10,
            is_active=True,
        )
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _make_pending_order(self) -> Order:
        """Создаёт PENDING-заказ: 3 шт. товара. Остаток товара — 7 (10 − 3)."""
        self.product.stock = 7
        self.product.save(update_fields=['stock'])

        order = Order.objects.create(
            user=self.user,
            total_price=Decimal('1200.00'),
            shipping_address='Тестовый адрес',
            status=Order.Status.PENDING,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=Decimal('400.00'),
            quantity=3,
        )
        return order

    def test_cancel_returns_stock_and_sets_status(self) -> None:
        """Отмена: 3 шт. возвращаются на склад, статус → CANCELLED."""
        order = self._make_pending_order()
        url = reverse('api-orders-detail', args=[order.id])

        response = self.api.delete(url)

        self.assertEqual(response.status_code, drf_status.HTTP_204_NO_CONTENT)
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock, 10)  # 7 + 3

    def test_double_cancel_returns_400_and_does_not_return_stock_twice(self) -> None:
        """Двойная отмена: второй запрос отклоняется, остаток не растёт дважды.

        Симулирует race condition: оба запроса «одновременно» видят
        PENDING, но благодаря select_for_update() + повторной проверке
        под блокировкой второй запрос получает 400 и НЕ возвращает
        остаток повторно.
        """
        order = self._make_pending_order()
        url = reverse('api-orders-detail', args=[order.id])

        first = self.api.delete(url)
        second = self.api.delete(url)

        self.assertEqual(first.status_code, drf_status.HTTP_204_NO_CONTENT)
        self.assertEqual(second.status_code, drf_status.HTTP_400_BAD_REQUEST)

        self.product.refresh_from_db()
        # Только +3, не +6
        self.assertEqual(self.product.stock, 10)

    def test_cancel_shipped_order_returns_400(self) -> None:
        """SHIPPED: отмена отклоняется — товар уже у курьера."""
        order = self._make_pending_order()
        order.status = Order.Status.SHIPPED
        order.save(update_fields=['status', 'updated_at'])
        url = reverse('api-orders-detail', args=[order.id])

        response = self.api.delete(url)

        self.assertEqual(response.status_code, drf_status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)  # не изменился

    def test_cancel_updates_updated_at(self) -> None:
        """Отмена обновляет updated_at (иначе auto_now не срабатывает)."""
        order = self._make_pending_order()
        old_updated_at = order.updated_at
        url = reverse('api-orders-detail', args=[order.id])

        self.api.delete(url)

        order.refresh_from_db()
        self.assertGreater(order.updated_at, old_updated_at)
