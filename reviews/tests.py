"""
Модульные тесты приложения отзывов и оценок покупателей.

Реализует проверку бизнес-правил по разделам 3.2, 3.7, 4 и 6.3 ТЗ:
- Запрет отзыва без подтвержденного факта покупки;
- Проверка уникальности отзыва от одного пользователя на товар;
- Валидация диапазона рейтинга (1–5);
- Работа REST API эндпоинта /api/products/<id>/reviews/.
"""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from orders.models import Order, OrderItem
from products.models import Category, Product
from .models import Review

User = get_user_model()


class ReviewBusinessLogicTestCase(TestCase):
    """Тестирование бизнес-правил веб-интерфейса и ORM-ограничений отзывов."""

    def setUp(self) -> None:
        """Инициализация тестового окружения и базовых данных."""
        self.user = User.objects.create_user(
            username='brewer_john',
            email='john@example.com',
            password='secure_password_123',
        )
        self.other_user = User.objects.create_user(
            username='brewer_bob',
            email='bob@example.com',
            password='secure_password_123',
        )
        self.category = Category.objects.create(name='Хмель', slug='hops')
        self.product = Product.objects.create(
            name='Хмель Citra (100г)',
            slug='citra-hops-100g',
            price=Decimal('550.00'),
            category=self.category,
            stock=20,
            is_active=True,
        )

    def test_cannot_review_without_purchase(self) -> None:
        """Пользователь без оформленного и оплаченного заказа не может оставить отзыв (раздел 3.2 ТЗ)."""
        self.client.login(username='john@example.com', password='secure_password_123')

        payload = {'rating': 5, 'comment': 'Отличный цитрусовый аромат!'}
        response = self.client.post(
            reverse('reviews:add_review', kwargs={'product_id': self.product.id}),
            data=payload,
        )

        self.assertRedirects(response, self.product.get_absolute_url())
        self.assertFalse(Review.objects.filter(product=self.product, user=self.user).exists())

    def test_cannot_review_with_pending_unpaid_order(self) -> None:
        """Заказ в статусе 'PENDING' (не оплачен) не дает права оставить отзыв."""
        self.client.login(username='john@example.com', password='secure_password_123')

        # Создаем неоплаченный заказ
        order = Order.objects.create(
            user=self.user,
            total_price=Decimal('550.00'),
            status=Order.Status.PENDING,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=Decimal('550.00'),
            quantity=1,
        )

        payload = {'rating': 5, 'comment': 'Пока не оплатил, но хмель отличный!'}
        self.client.post(
            reverse('reviews:add_review', kwargs={'product_id': self.product.id}),
            data=payload,
        )

        self.assertFalse(Review.objects.filter(product=self.product, user=self.user).exists())

    def test_can_review_after_successful_paid_purchase(self) -> None:
        """Пользователь успешно создает отзыв после оплаты заказа (раздел 3.2 ТЗ)."""
        self.client.login(username='john@example.com', password='secure_password_123')

        # Создаем оплаченный заказ
        order = Order.objects.create(
            user=self.user,
            total_price=Decimal('550.00'),
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=Decimal('550.00'),
            quantity=1,
        )

        payload = {'rating': 5, 'comment': 'Яркий хмель, сварил идеальный IPA!'}
        response = self.client.post(
            reverse('reviews:add_review', kwargs={'product_id': self.product.id}),
            data=payload,
        )

        self.assertRedirects(response, self.product.get_absolute_url())
        review = Review.objects.filter(product=self.product, user=self.user).first()
        self.assertIsNotNone(review)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, 'Яркий хмель, сварил идеальный IPA!')

    def test_cannot_review_same_product_twice(self) -> None:
        """Пользователь не может отправить повторный отзыв на один и тот же товар (раздел 4 ТЗ)."""
        self.client.login(username='john@example.com', password='secure_password_123')

        # Создаем заказ
        order = Order.objects.create(
            user=self.user,
            total_price=Decimal('550.00'),
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=Decimal('550.00'),
            quantity=1,
        )

        # Первый отзыв
        Review.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            comment='Первый отзыв покупателя',
        )

        # Попытка добавить второй отзыв через веб-форму
        payload = {'rating': 4, 'comment': 'Попытка повторного отзыва'}
        self.client.post(
            reverse('reviews:add_review', kwargs={'product_id': self.product.id}),
            data=payload,
        )

        self.assertEqual(Review.objects.filter(product=self.product, user=self.user).count(), 1)

    def test_unique_constraint_at_database_level(self) -> None:
        """Проверка срабатывания UniqueConstraint на уровне базы данных (раздел 4 ТЗ)."""
        Review.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            comment='Первый отзыв',
        )

        with self.assertRaises(IntegrityError):
            Review.objects.create(
                product=self.product,
                user=self.user,
                rating=3,
                comment='Второй дублирующий отзыв',
            )

    def test_rating_validators_range(self) -> None:
        """Проверка валидаторов допустимого рейтинга (только от 1 до 5) (раздел 3.2 ТЗ)."""
        invalid_review_high = Review(
            product=self.product,
            user=self.other_user,
            rating=6,
            comment='Слишком высокая оценка',
        )
        with self.assertRaises(ValidationError):
            invalid_review_high.full_clean()

        invalid_review_low = Review(
            product=self.product,
            user=self.other_user,
            rating=0,
            comment='Слишком низкая оценка',
        )
        with self.assertRaises(ValidationError):
            invalid_review_low.full_clean()


class ReviewAPITestCase(TestCase):
    """Тестирование эндпоинта REST API /api/products/<id>/reviews/ (раздел 3.7 ТЗ)."""

    def setUp(self) -> None:
        """Инициализация тестовых клиентов DRF и JWT-токенов."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='api_buyer',
            email='api_buyer@example.com',
            password='strong_password_123',
        )
        self.category = Category.objects.create(name='Дрожжи', slug='yeast')
        self.product = Product.objects.create(
            name='Дрожжи SafAle US-05',
            slug='safale-us-05',
            price=Decimal('390.00'),
            category=self.category,
            stock=15,
            is_active=True,
        )

        # Выпуск JWT-токена
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)

    def test_get_reviews_list_unauthorized(self) -> None:
        """Список отзывов к товару доступен без авторизации (GET запрос)."""
        Review.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            comment='Отличные чистые дрожжи!',
        )

        url = reverse('api-product-reviews', kwargs={'product_id': self.product.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['rating'], 5)
        self.assertEqual(response.data[0]['user'], self.user.username)

    def test_post_review_unauthorized_fails(self) -> None:
        """Анонимный запрос на добавление отзыва через API отклоняется (401 Unauthorized)."""
        url = reverse('api-product-reviews', kwargs={'product_id': self.product.id})
        payload = {'rating': 5, 'comment': 'Анонимный отзыв'}
        response = self.client.post(url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_review_without_purchase_fails(self) -> None:
        """Авторизованный пользователь без покупки получает 403 Forbidden."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        url = reverse('api-product-reviews', kwargs={'product_id': self.product.id})
        payload = {'rating': 5, 'comment': 'Попытка оставить отзыв без покупки'}
        response = self.client.post(url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_post_review_after_purchase_success(self) -> None:
        """Авторизованный покупатель с оплаченным заказом успешно публикует отзыв через API."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

        # Создаем оплаченный заказ для пользователя
        order = Order.objects.create(
            user=self.user,
            total_price=Decimal('390.00'),
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            price=Decimal('390.00'),
            quantity=1,
        )

        url = reverse('api-product-reviews', kwargs={'product_id': self.product.id})
        payload = {'rating': 5, 'comment': 'Быстро завелись, сбродили насухо!'}
        response = self.client.post(url, data=payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['rating'], 5)
        self.assertEqual(response.data['comment'], 'Быстро завелись, сбродили насухо!')
