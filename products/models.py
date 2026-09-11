"""Модели базы данных для категорий и товаров каталога."""

from django.db import models
from django.urls import reverse
from django.db.models import Index

class Category(models.Model):
    """Категория товаров с поддержкой иерархической вложенности."""

    name: models.CharField = models.CharField(
        max_length=255,
        verbose_name="Название",
    )
    slug: models.SlugField = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name="Slug",
    )
    parent: models.ForeignKey = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория",
    )
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )
    updated_at: models.DateTimeField = models.DateTimeField(
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
    """Товар интернет-магазина крафтовых напитков."""

    name: models.CharField = models.CharField(
        max_length=255,
        verbose_name="Название",
    )
    slug: models.SlugField = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name="Slug",
    )
    description: models.TextField = models.TextField(
        blank=True,
        verbose_name="Описание",
    )
    price: models.DecimalField = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Цена",
    )
    category: models.ForeignKey = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Категория",
    )
    image: models.ImageField = models.ImageField(
        upload_to="products/%Y/%m/",
        blank=True,
        null=True,
        verbose_name="Изображение товара",
    )
    is_active: models.BooleanField = models.BooleanField(
        default=True,
        verbose_name="Активен",
    )
    stock: models.PositiveIntegerField = models.PositiveIntegerField(
        default=0,
        verbose_name="Остаток на складе",
    )
    created_at: models.DateTimeField = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата добавления",
    )
    updated_at: models.DateTimeField = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата изменения",
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["-created_at"]),
            models.Index(fields=["price"]),
        ]

    def __str__(self) -> str:
        """Строковое представление товара."""
        return str(self.name)

    def get_absolute_url(self) -> str:
        """Возвращает URL детальной страницы карточки товара."""
        return reverse("products:detail", kwargs={"slug": self.slug})

    @property
    def in_stock(self) -> bool:
        """Проверяет фактическое наличие товара на складе."""
        return bool(self.stock > 0)