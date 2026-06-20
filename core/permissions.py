from rest_framework.permissions import BasePermission

from core.models import Center, Visitor, Queue



class IsOwnerOrCenterManager(BasePermission):
    """
    Object-level permission:
      - Center: only center.user (the manager) can access.
      - Visitor: owner (visitor.user) OR a center manager who manages any center
                 that has this visitor in its queues.
      - Queue: center manager (queue.center.user) OR the visitor who owns the queue.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Center object: only center owner (manager)
        if isinstance(obj, Center):
            return obj.user == user

        # Visitor object: owner OR manager of any center that has this visitor in its queues
        if isinstance(obj, Visitor):
            if obj.user == user:
                return True

            if getattr(user, "is_center_manager", False):
                # Fast existence check: is there any Queue that links this visitor to a center owned by user?
                return Queue.objects.filter(visitor=obj, center__user=user).exists()

            return False

        # Queue object: center manager (of that center) OR the visitor's user
        if isinstance(obj, Queue):
            if getattr(user, "is_center_manager", False) and obj.center.user == user:
                return True
            return obj.visitor.user == user

        return False
