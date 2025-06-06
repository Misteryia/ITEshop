from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from init_db import Cart, CartItem
from sqlalchemy.orm import selectinload
from sqlalchemy import delete
from metrics import db_metr
import httpx

@db_metr(operation="get_cart_items")
async def get_cart_items(db: AsyncSession, user_id: int):
    cart_result = await db.execute(select(Cart).filter(Cart.user_id == user_id))
    cart = cart_result.scalar_one_or_none()

    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    cart_items_result = await db.execute(select(CartItem).filter(CartItem.cart_id == cart.id))
    cart_items = cart_items_result.scalars().all()

    items = [
        {"product_id": item.product_id, "quantity": item.quantity}
        for item in cart_items
    ]
    print("DEBUG: cart items: ", items)

    return items

@db_metr(operation="get_cart_by_user_id")
async def get_cart_by_user_id(db: AsyncSession, user_id: int):
    result = await db.execute(select(Cart).filter(Cart.user_id == user_id))
    return result.scalar_one_or_none()

@db_metr(operation="add_product_to_cart")
async def add_product_to_cart(db: AsyncSession, user_id: int, product_id: int, quantity: int = 1):
    cart = await get_cart_by_user_id(db, user_id)
    print("DEBUG CART SERVICE add_product_to_cart, cart: ", cart)
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    cart_item = await db.execute(select(CartItem).filter(CartItem.product_id == product_id, CartItem.cart_id == cart.id))
    cart_item = cart_item.scalar_one_or_none()

    if cart_item:
        cart_item.quantity += quantity
    else:
        new_item = CartItem(product_id=product_id, quantity=quantity, cart_id=cart.id)
        db.add(new_item)
    
    await db.commit()
    return cart


@db_metr(operation="get_cart_with_items")
async def get_cart_with_items(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(selectinload(Cart.items))  
    )
    cart = result.scalar_one_or_none()

    if not cart:
        return None

    cart_dict = {
        "id": cart.id,
        "user_id": cart.user_id,
        "cart_items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
            }
            for item in cart.items
        ]
    }

    return cart_dict


@db_metr(operation="clear_user_cart")
async def clear_user_cart(db: AsyncSession, user_id: int):
    cart = await db.execute(select(Cart).filter(Cart.user_id == user_id))
    cart = cart.scalar_one_or_none()

    if cart:
        await db.execute(delete(CartItem).filter(CartItem.cart_id == cart.id))
        await db.commit()  


@db_metr(operation="remove_product_from_cart")
async def remove_product_from_cart(db: AsyncSession, user_id: int, product_id: int):

    cart = await get_cart_by_user_id(db, user_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    
    cart_item = await db.execute(select(CartItem).filter(CartItem.product_id == product_id, CartItem.cart_id == cart.id))
    cart_item = cart_item.scalar_one_or_none()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Product not found in the cart")
    await db.delete(cart_item)
    await db.commit()
    return cart

@db_metr(operation="update_product_quantity_in_cart")
async def update_product_quantity_in_cart(db: AsyncSession, user_id: int, product_id: int, quantity: int):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero.")

    cart = await get_cart_by_user_id(db, user_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://catalog:8003/api/get_product?id={product_id}")
        if resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Product not found in catalog")
        product = resp.json()
        stock = product.get("stock", 0)
        if quantity > stock:
            raise HTTPException(status_code=400, detail=f"Максимальное количество для заказа: {stock}")

    cart_item = await db.execute(select(CartItem).filter(CartItem.product_id == product_id, CartItem.cart_id == cart.id))
    cart_item = cart_item.scalar_one_or_none()

    if not cart_item:
        raise HTTPException(status_code=404, detail="Product not found in the cart")

    cart_item.quantity = quantity
    await db.commit()
    return cart

@db_metr(operation="get_all_cart_items")
async def get_all_cart_items(db: AsyncSession, user_id: int):
    cart = await get_cart_by_user_id(db, user_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    return cart.items
