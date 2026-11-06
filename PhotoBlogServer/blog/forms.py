from django import forms
from .models import Post

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['title', 'text', 'image']
        widgets = {'text': forms.Textarea(attrs={'rows': 4}), 'image': forms.ClearableFileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'})}

    def clean_image(self):
        image = self.cleaned_data['image']
        if image.size > 8 * 1024 * 1024:
            raise forms.ValidationError('이미지는 8MB 이하여야 합니다.')
        if image.image.format not in ('JPEG', 'PNG', 'WEBP'):
            raise forms.ValidationError('JPEG, PNG, WEBP 이미지를 사용해주세요.')
        return image
