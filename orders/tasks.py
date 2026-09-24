"""Фоновые задачи приложения orders.

Email-уведомления вынесены из сериализаторов в Celery-задачи по двум причинам:

1. Чекаут не должен блокироваться на SMTP. Сейчас `send_mail` может ждать
   200–500 мс, а при недоступности SMTP — висеть до таймаута.
2. Уведомления не должны теряться при сбое SMTP. Celery делает retry
   с backoff, а Django-транзакция чекаута не откатывается из-за проблем
   с почтой.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import mail_admins, send_mail

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_confirmation(self, order_id: int) -> None:
    """Отправляет письмо-подтверждение покупателю.

    При сбое SMTP — до 3 повторов с интервалом 60 секунд.
    После — сдаётся и логирует (retry вернёт MaxRetriesExceededError).

    Args:
        order_id: ID заказа.
    """
    from orders.models import Order  # локальный импорт — избегаем цикла

    try:
        order = Order.objects.select_related('user').get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning('Order #%s not found, skip email', order_id)
        return

    user = order.user

    try:
        send_mail(
            subject=f'Hop & Barley: Заказ #{order.id} принят в обработку',
            message=(
                f'Здравствуйте, {user.get_full_name() or user.username}!\n\n'
                f'Ваш заказ #{order.id} на сумму {order.total_price} ₽ успешно создан.\n'
                f'Способ оплаты: {order.get_payment_method_display()}.\n'
                f'Адрес доставки: {order.shipping_address}\n\n'
                'Спасибо, что выбрали Hop & Barley!'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,  # важно: raise → Celery retry
        )
    except Exception as exc:
        logger.exception('Failed to send order email #%s', order_id)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def notify_admins_new_order(self, order_id: int) -> None:
    """Уведомляет администраторов о новом заказе.

    Args:
        order_id: ID заказа.
    """
    from orders.models import Order

    try:
        order = Order.objects.select_related('user').get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning('Order #%s not found, skip admin notification', order_id)
        return

    try:
        mail_admins(
            subject=f'Новый заказ #{order.id} на сумму {order.total_price} ₽',
            message=f'Пользователь {order.user.username} оформил заказ #{order.id}.',
            fail_silently=False,
        )
    except Exception as exc:
        logger.exception('Failed to notify admins about order #%s', order_id)
        raise self.retry(exc=exc) from exc
