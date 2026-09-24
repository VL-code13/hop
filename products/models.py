"""Модели базы данных для категорий и товаров каталога."""

from django.core.validators import MinValueValidator
from django.db import models
from django.templatetags.static import static
from django.urls import reverse

# Соответствие ключевых слов в названии/slug товара → статичной картинке.
# Порядок важен: специфичные ключи (chocolate, caramunich) должны идти
# раньше общих (pale ale, pilsner), иначе сработает первое совпадение.
# Регистр игнорируется (`haystack.lower()`).
IMAGE_KEYWORD_MAP: tuple[tuple[tuple[str, ...], str], ...] = (
    # ── Солод ──────────────────────────────────────────────
    (('chocolate', 'шоколад'), 'img/products/caramel_malt.jpg'),
    (('caramunich', 'карамельн'), 'img/products/caramel_malt.jpg'),
    (('maris', 'otter', 'pale ale', 'pale-ale'), 'img/products/maris_otter_malt.jpg'),
    (('pilsner', 'пилзнер', 'пилснер'), 'img/products/pilsner_malt.jpg'),
    (('wheat', 'пшенич', 'unmalted'), 'img/products/unmalted_wheat.jpg'),
    # ── Хмель ──────────────────────────────────────────────
    (('citra', 'цитра'), 'img/products/citra_hops.jpg'),
    (('mosaic', 'мозаик'), 'img/products/mosaic_hops.jpg'),
    (('saaz', 'жатецкий', 'сааз'), 'img/products/saaz_hops.jpg'),
    (('magnum', 'магнум'), 'img/products/centennial_hops.jpg'),
    (('cascade', 'каскад'), 'img/products/cascade_hops.jpg'),
    (('centennial', 'сентенниал'), 'img/products/centennial_hops.jpg'),
    # ── Дрожжи ─────────────────────────────────────────────
    (('safale', 'us-05', 'us05'), 'img/products/safale_us05_yeast.jpg'),
    (('saflager', 'w-34', 'w34'), 'img/products/imperial_yeast.jpg'),
    (('imperial', 'империал'), 'img/products/imperial_yeast.jpg'),
    # ── Наборы ─────────────────────────────────────────────
    (('kit', 'набор'), 'img/products/ipa_kit.jpg'),
)

# Fallback по slug категории — срабатывает, если ни одно ключевое
# слово не совпало. Категория `equipment` намеренно отсутствует: для
# оборудования нет подходящих фото, будет использован DEFAULT_PRODUCT_IMAGE.
CATEGORY_IMAGE_MAP: dict[str, str] = {
    'yeast': 'img/products/safale_us05_yeast.jpg',
    'malts': 'img/products/pilsner_malt.jpg',
    'aroma-hops': 'img/products/citra_hops.jpg',
    'bittering-hops': 'img/products/centennial_hops.jpg',
}

# Общий placeholder — если ни image, ни keyword, ни категория не сработали.
DEFAULT_PRODUCT_IMAGE: str = 'img/no-image.png'


class Category(models.Model):
    """Категория товаров с поддержкой иерархической вложенности."""

    name = models.CharField(max_length=255, verbose_name='Название')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='Родительская категория',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self) -> str:
        return str(self.name)

    def get_absolute_url(self) -> str:
        return reverse('products:list_by_category', kwargs={'category_slug': self.slug})


class Product(models.Model):
    """Товар интернет-магазина крафтового пивоварения Hop & Barley."""

    name = models.CharField(max_length=255, verbose_name='Название')
    slug = models.SlugField(max_length=255, unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Описание')
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name='Цена',
        help_text='Текущая розничная цена за единицу товара.',
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='Категория',
        help_text='Категория, к которой привязан товар.',
    )
    image = models.ImageField(
        upload_to='products/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Изображение товара',
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен',
        help_text='Отображать ли товар на витрине магазина.',
    )
    stock = models.PositiveIntegerField(
        default=0,
        verbose_name='Остаток на складе',
        help_text='Количество доступных для заказа единиц.',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата изменения')

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['price']),
        ]

    def __str__(self) -> str:
        return str(self.name)

    def get_absolute_url(self) -> str:
        return reverse('products:product_detail', kwargs={'slug': self.slug})

    @property
    def in_stock(self) -> bool:
        """Проверяет фактическое наличие товара на складе."""
        return bool(self.stock > 0)

    @property
    def display_image_url(self) -> str:
        """URL картинки товара с четырёхуровневым fallback.

        Приоритет:

        1. Загруженное пользователем ``image`` (медиа).
        2. Совпадение ключевых слов в ``name`` или ``slug`` с
           ``IMAGE_KEYWORD_MAP`` — например, «Хмель Citra» → ``citra_hops.jpg``.
        3. Совпадение ``category.slug`` с ``CATEGORY_IMAGE_MAP``.
        4. Общий placeholder ``img/no-image.png``.

        Используется в шаблонах вместо ``{% if product.image %}``,
        чтобы у каждого товара гарантированно была осмысленная картинка.
        """
        if self.image:
            return self.image.url

        haystack = f'{self.name} {self.slug}'.lower()
        for keywords, image_path in IMAGE_KEYWORD_MAP:
            if any(kw in haystack for kw in keywords):
                return static(image_path)

        if self.category_id and self.category.slug in CATEGORY_IMAGE_MAP:
            return static(CATEGORY_IMAGE_MAP[self.category.slug])

        return static(DEFAULT_PRODUCT_IMAGE)
