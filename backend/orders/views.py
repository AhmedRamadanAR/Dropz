from rest_framework import status, viewsets, permissions
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Order, OrderItem
from .serializers import OrderSerializer
from addresses.models import Address
from carts.models import CartItem, Cart


class IsOwnerOrStaff(permissions.BasePermission):
    """Allow only order owner or staff"""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrStaff]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all().order_by("-created_at")
        return Order.objects.filter(user=user).order_by("-created_at")

    def perform_update(self, serializer):
        # Prevent changing status directly unless staff
        if (
            not self.request.user.is_staff
            and "status" in serializer.validated_data
        ):
            raise PermissionDenied("You cannot update order status manually.")
        serializer.save()


class CheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user

        # Get cart_id from request
        cart_id = request.data.get("cart_id")
        
        if not cart_id:
            return Response(
                {"detail": "Cart ID is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate and get the cart
        try:
            cart = Cart.objects.get(id=cart_id, user=user)
        except Cart.DoesNotExist:
            return Response(
                {"detail": "Cart not found or doesn't belong to you."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get all cart items for this cart
        cart_items = CartItem.objects.filter(
            cart=cart
        ).select_related("product")

        if not cart_items.exists():
            return Response(
                {"detail": "Cart is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate stock and availability
        unavailable_items = []
        out_of_stock_items = []

        for item in cart_items:
            if not item.product.is_active:
                unavailable_items.append(item.product.title)
            elif item.quantity > item.product.stock_quantity:
                out_of_stock_items.append(
                    {
                        "product": item.product.title,
                        "requested": item.quantity,
                        "available": item.product.stock_quantity,
                    }
                )

        if unavailable_items:
            return Response(
                {
                    "detail": "Some products are no longer available.",
                    "unavailable_products": unavailable_items,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if out_of_stock_items:
            return Response(
                {
                    "detail": "Insufficient stock for some products.",
                    "out_of_stock_products": out_of_stock_items,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get shipping address
        shipping_address_id = request.data.get("shipping_address_id")
        shipping_address = None

        if shipping_address_id:
            try:
                shipping_address = Address.objects.get(
                    id=shipping_address_id,
                    user=user,
                )
            except Address.DoesNotExist:
                return Response(
                    {"detail": "Invalid address."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # Fallback to default address
            shipping_address = Address.objects.filter(
                user=user,
                is_default=True,
            ).first()
            if not shipping_address:
                return Response(
                    {"detail": "No shipping address found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Create order
        order = Order.objects.create(
            user=user,
            status="pending",
            shipping_address=shipping_address,
        )

        # Convert all cart items -> order items
        order_items = [
            OrderItem(
                order=order,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.product.price,  # snapshot current price
            )
            for item in cart_items
        ]
        OrderItem.objects.bulk_create(order_items)

        # Clear the entire cart after checkout
        cart_items.delete()

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_201_CREATED,
        )