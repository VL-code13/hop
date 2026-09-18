"""Модели базы данных для категорий и товаров каталога."""

from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Category(models.Model):
    """Категория товаров с поддержкой иерархической вложенности."""

    name = models.CharField(
        max_length=255,
        verbose_name="Название",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name="Slug",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["name"]

    def __str__(self) -> str:
        """Строковое представление категории."""
        return str(self.name)

    def get_absolute_url(self) -> str:
        """Возвращает URL списка товаров, отфильтрованных по текущей категории."""
        return reverse("products:list_by_category", kwargs={"category_slug": self.slug})


class Product(models.Model):
    """
    Товар интернет-магазина крафтового пивоварения Hop & Barley.

    Хранит информацию о стоимости, остатках на складе, изображениях
    и статусе активности (раздел 4 ТЗ).
    """

    name = models.CharField(
        max_length=255,
        verbose_name="Название",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name="Slug",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Описание",
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Цена",
        help_text='Текущая розничная цена за единицу товара.',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Категория",
        help_text='Категория, к которой привязан товар.',
    )
    image = models.ImageField(
        upload_to="products/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="Изображение товара",
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text='Отображать ли товар на витрине магазина.',
    )
    stock = models.PositiveIntegerField(
        default=0,
        verbose_name="Остаток на складе",
        help_text='Количество доступных для заказа единиц.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата добавления",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата изменения",
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["price"]),
        ]

    def __str__(self) -> str:
        """Строковое представление товара."""
        return str(self.name)

    def get_absolute_url(self) -> str:
        """Возвращает URL детальной страницы карточки товара."""
        return reverse("products:product_detail", kwargs={"slug": self.slug})

    @property
    def in_stock(self) -> bool:
        """Проверяет фактическое наличие товара на складе.
        Возвращает True, если физический остаток на складе строго больше 0."""
        return bool(self.stock > 0)
