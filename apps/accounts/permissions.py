from rest_framework import permissions

class IsCustomer(permissions.BasePermission):
    """
    Permission check for customer role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_customer()
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsRestaurantOwner(permissions.BasePermission):
    """
    Permission check for restaurant owner role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_restaurant_owner()
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsDeliveryRider(permissions.BasePermission):
    """
    Permission check for delivery rider role
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_delivery_rider()
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsAdminUser(permissions.BasePermission):
    """
    Permission check for admin users (staff, superuser, or admin role)
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin_user()
    
    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission that allows access only to the owner of the object or admin
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin_user():
            return True
        
        # Check if the object has a 'user' attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if the object is the user itself
        if hasattr(obj, 'id') and obj == request.user:
            return True
        
        # Check for restaurant owner
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        return False


class IsRestaurantOwnerOrAdmin(permissions.BasePermission):
    """
    Permission for restaurant owners to access their own restaurants and admin full access
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_admin_user() or request.user.is_restaurant_owner()
        )
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin_user():
            return True
        
        # For restaurant model
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        
        # For menu item model
        if hasattr(obj, 'restaurant') and hasattr(obj.restaurant, 'owner'):
            return obj.restaurant.owner == request.user
        
        return False


class IsDeliveryRiderOrAdmin(permissions.BasePermission):
    """
    Permission for delivery riders to access delivery-related endpoints
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_admin_user() or request.user.is_delivery_rider()
        )
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin_user():
            return True
        
        # For order model - rider can only access orders assigned to them
        if hasattr(obj, 'rider'):
            return obj.rider == request.user
        
        # For user model - rider can only update their own location
        if hasattr(obj, 'is_delivery_rider') and obj == request.user:
            return True
        
        return False


class IsCustomerOrAdmin(permissions.BasePermission):
    """
    Permission for customers to access customer-specific endpoints
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_admin_user() or request.user.is_customer()
        )
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin_user():
            return True
        
        # For order model - customer can only access their own orders
        if hasattr(obj, 'customer'):
            return obj.customer == request.user
        
        return False


class AllowAnyPostOnly(permissions.BasePermission):
    """
    Allow any user to POST (register/login), but require auth for other methods
    """
    def has_permission(self, request, view):
        if request.method == 'POST':
            return True
        return request.user and request.user.is_authenticated