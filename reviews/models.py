from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from django.conf import settings
from products.models import Product


# Create your models here.
class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['product', 'user'], name='unique_review_per_user', )]

    def __str__(self):
        return f'{self.user} -> {self.product} ({self.rating})'
