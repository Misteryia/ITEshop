from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from init_db import User, Wishlist, Order, OrderItem, Seller, UserBase, OrderItemBase, OrderBase, SellerRegister
from sqlalchemy.orm import selectinload
from metrics import db_metr

# Функция для получения всех пользователей
@db_metr(operation="get_all_users")
async def get_all_users(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

# Функция для получения пользователя по ID
@db_metr(operation="get_user_by_id")
async def get_user_by_id(db: AsyncSession, user_id: int):
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalar_one_or_none()

@db_metr(operation="get_user_by_email")
async def get_user_by_email(db: AsyncSession, email: str):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

@db_metr(operation="get_user_with_details")
async def get_user_with_details(db: AsyncSession, email: str):
    user = await get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
    }

    if user_data["role"] == "seller":
        seller_result = await db.execute(select(Seller).filter(Seller.user_id == user.id))
        seller = seller_result.scalar_one_or_none()
        if seller:
            user_data["seller_info"] = {
                "shop_name": seller.shop_name,
                "inn": seller.inn,
                "description": seller.description
            }
        else:
            user_data["seller_info"] = None
    else:
        wishlist_result = await db.execute(select(Wishlist).filter(Wishlist.user_id == user.id))
        wishlist = wishlist_result.scalars().all()
        orders_result = await db.execute(select(Order).filter(Order.user_id == user.id))
        orders = orders_result.scalars().all()
        orders_with_items = []
        for order in orders:
            order_items_result = await db.execute(select(OrderItem).filter(OrderItem.order_id == order.id))
            order_items = order_items_result.scalars().all()
            orders_with_items.append({
                "order_id": order.id,
                "status": order.status,
                "items": [
                    {"product_id": item.product_id, "quantity": item.quantity}
                    for item in order_items
                ]
            })
        user_data["wishlist"] = [
            {"product_id": item.product_id} for item in wishlist
        ]
        user_data["orders"] = orders_with_items

    return user_data

@db_metr(operation="create_user")
async def create_user(db: AsyncSession, user_data: dict):
    print("DEBUG: auth function create_user, user_data:", user_data)
    db_user = User(
        email=user_data['email'],
        hashed_password=user_data['hashed_password'],
        is_active=user_data['is_active']
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@db_metr(operation="update_user")
async def update_user(db: AsyncSession, user_id: int, user_data: UserBase):
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.email = user_data.email
    db_user.hashed_password = user_data.hashed_password
    db_user.is_active = user_data.is_active
    await db.commit()
    await db.refresh(db_user)
    return db_user

@db_metr(operation="delete_user")
async def delete_user(db: AsyncSession, user_id: int):
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.delete(db_user)
    await db.commit()
    return db_user

@db_metr(operation="add_to_wishlist")
async def add_to_wishlist(db: AsyncSession, user_id: int, product_id: int):
    # Проверка существования пользователя
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Проверка, не добавлен ли уже товар
    db_wishlist = await db.execute(select(Wishlist).filter(Wishlist.user_id == user_id, Wishlist.product_id == product_id))
    existing_item = db_wishlist.scalar_one_or_none()
    if existing_item:
        raise HTTPException(status_code=400, detail="Product already in wishlist")
    
    new_wishlist_item = Wishlist(user_id=user_id, product_id=product_id)
    db.add(new_wishlist_item)
    await db.commit()
    await db.refresh(new_wishlist_item)
    return new_wishlist_item

@db_metr(operation="remove_from_wishlist")
async def remove_from_wishlist(db: AsyncSession, user_id: int, product_id: int):
    db_wishlist = await db.execute(select(Wishlist).filter(Wishlist.user_id == user_id, Wishlist.product_id == product_id))
    wishlist_item = db_wishlist.scalar_one_or_none()
    if not wishlist_item:
        raise HTTPException(status_code=404, detail="Wishlist item not found")
    
    await db.delete(wishlist_item)
    await db.commit()
    return wishlist_item

@db_metr(operation="create_order")
async def create_order(db: AsyncSession, user_id: int, order_data: OrderBase, order_items: list[OrderItemBase]):
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    new_order = Order(user_id=user_id, status=order_data.status)
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)

    for item in order_items:
        order_item = OrderItem(order_id=new_order.id, product_id=item.product_id, quantity=item.quantity)
        db.add(order_item)
    
    await db.commit()
    await db.refresh(new_order)
    return new_order

@db_metr(operation="get_user_orders")
async def get_user_orders(db: AsyncSession, user_id: int, skip: int = 0, limit: int = 100):
    db_user = await get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    result = await db.execute(select(Order).filter(Order.user_id == user_id).offset(skip).limit(limit))
    return result.scalars().all()

@db_metr(operation="get_order_with_items")
async def get_order_with_items(db: AsyncSession, order_id: int):
    result = await db.execute(
        select(Order)
        .filter(Order.id == order_id)
        .options(selectinload(Order.order_items))
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@db_metr(operation="create_seller")
async def create_seller(db: AsyncSession, user_id: int, seller_data: dict):
    db_seller = Seller(
        user_id=user_id,
        shop_name=seller_data['shop_name'],
        inn=seller_data.get('inn'),
        description=seller_data.get('description')
    )
    db.add(db_seller)
    await db.commit()
    await db.refresh(db_seller)
    return db_seller

@db_metr(operation="register_seller")
async def register_seller(db: AsyncSession, seller_data: SellerRegister):
    existing_user = await get_user_by_email(db, seller_data.email)
    if existing_user:
        raise HTTPException(status_code=400, detail=f"User {seller_data.email} already exists")
    db_user = User(
        email=seller_data.email,
        hashed_password=seller_data.password, 
        is_active=True,
        role='seller'
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    db_seller = Seller(
        user_id=db_user.id,
        shop_name=seller_data.shop_name,
        inn=seller_data.inn,
        description=seller_data.description
    )
    db.add(db_seller)
    await db.commit()
    await db.refresh(db_seller)
    return db_user, db_seller

@db_metr(operation="get_seller_by_user_id")
async def get_seller_by_user_id(db: AsyncSession, user_id: int):
    seller_result = await db.execute(select(Seller).filter(Seller.user_id == user_id))
    seller = seller_result.scalar_one_or_none()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    return seller
