"""Формы ввода и валидации пользовательских отзывов."""

from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    """Форма добавления отзыва на купленный товар."""

    class Meta:
        model = Review
        fields = ('rating', 'comment')
        widgets = {
            'rating': forms.Select(
                choices=[(i, f"{i} зв.") for i in range(5, 0, -1)],
                attrs={'class': 'search-input', 'style': 'width: 120px;'},
            ),
            'comment': forms.Textarea(
                attrs={
                    'class': 'form-input',
                    'rows': 4,
                    'placeholder': 'Поделитесь впечатлениями о вкусе, аромате или качестве...',
                    'required': True,
                }
            ),
        }
        labels = {
            'rating': 'Ваша оценка',
            'comment': 'Комментарий',
        }