import random
from django.db import models
from accounts.models import User

class Center(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, unique=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)
    avg_wait_seconds = models.DecimalField(
        max_digits=6,
        decimal_places=1,
        default=0,
        null=True,
        blank=True)

    def __str__(self):
        return self.name


class Visitor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    phone = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, blank=True)
    tag = models.CharField(max_length=50, blank=True, null=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"


class Queue(models.Model):
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='queues')
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='queues')
    position = models.PositiveIntegerField()  # Row number in the queue
    status = models.CharField(
        max_length=20,
        choices=[('waiting', 'Waiting'), ('in_progress', 'In Progress'), ('done', 'Done')],
        default='waiting'
    )

    access_token = models.CharField(max_length=32, unique=True, db_index=True, null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    token_expired = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['position']
        unique_together = ('center', 'position')

    def save(self, *args, **kwargs):
        if not self.access_token:
            self.access_token = generate_numeric_token(length=25)
            print(self.access_token)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.visitor.name} in {self.center.name} at position {self.position}"


# mBOTDgF2TQPXY6F41gTVRvaPXfiJ2PutjjbFda+9ewM

class Notification(models.Model):
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='notifications')
    phone = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)


class Rating(models.Model):
    """
    Rating given by a Visitor for a Center after their queue item is completed.
    Each (center, visitor) pair can have at most one rating (visitor can update).
    Score range: 0..5
    """
    center = models.ForeignKey(Center, on_delete=models.CASCADE, related_name='ratings')
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE, related_name='ratings')
    score = models.PositiveSmallIntegerField(default=0)  # 0..5
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('center', 'visitor')

    def __str__(self):
        return f"{self.visitor.phone} → {self.center.user_id}: {self.score}"