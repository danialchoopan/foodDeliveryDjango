from rest_framework import permissions
from apps.accounts.permissions import IsRestaurantOwnerOrAdmin, IsAdminUser, IsCustomerOrAdmin


class IsRestaurantOwnerOrReadOnly(permissions.BasePermission):
    """
    Restaurant owners can edit their own restaurants, others can only view
    """
    def has_permission(self, request, view):
        # List and retrieve are allowed for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Create, update, delete require restaurant owner or admin
        return request.user and request.user.is_authenticated and (
            request.user.is_admin_user() or request.user.is_restaurant_owner()
        )
    
    def has_object_permission(self, request, view, obj):
        # Read permissions
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions
        if request.user.is_admin_user():
            return True
        
        # Restaurant owner can only modify their own restaurant
        return obj.owner == request.user


class IsMenuOwnerOrAdmin(permissions.BasePermission):
    """
    Permission for menu items - owners can manage their restaurant's menu
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        return request.user and request.user.is_authenticated and (
            request.user.is_admin_user() or request.user.is_restaurant_owner()
        )
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if request.user.is_admin_user():
            return True
        
        # obj can be MenuItem or MenuCategory
        if hasattr(obj, 'restaurant'):
            return obj.restaurant.owner == request.user
        if hasattr(obj, 'category') and hasattr(obj.category, 'restaurant'):
            return obj.category.restaurant.owner == request.user
        
        return False


class CanManageRestaurantStatus(permissions.BasePermission):
    """
    Only restaurant owner or admin can change restaurant open/busy status
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin_user():
            return True
        return obj.owner == request.user


class CanViewRestaurantReports(permissions.BasePermission):
    """
    Only restaurant owner can view their own reports, admin can view all
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_admin_user() or request.user.is_restaurant_owner()
        )
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_admin_user():
            return True
        # obj can be a restaurant
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        # For report endpoints without object
        return True


class IsCustomerForMenuView(permissions.BasePermission):
    """
    Customers can view menu, but only when restaurant is active
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (
            request.user.is_customer() or 
            request.user.is_admin_user() or
            request.method in permissions.SAFE_METHODS
        )
    
    def has_object_permission(self, request, view, obj):
        # Any authenticated user can view menu items
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Only restaurant owner or admin can modify
        if request.user.is_admin_user():
            return True
        
        if hasattr(obj, 'restaurant'):
            return obj.restaurant.owner == request.user
        
        return False
    