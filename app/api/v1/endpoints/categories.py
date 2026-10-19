from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from api.deps import CurrentUser, SessionDep, require_roles
from models.inventory import Category
from models.user import UserRole
from schemas.inventory import CategoryCreate, CategoryResponse, CategoryUpdate

router = APIRouter()


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(session: SessionDep, current_user: CurrentUser):
    result = await session.execute(select(Category).order_by(Category.name))

    return result.scalars().all()


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))],
)
async def create_category(category_in: CategoryCreate, session: SessionDep):
    existing = await session.execute(
        select(Category).where(Category.name == category_in.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists",
        )

    category = Category(**category_in.model_dump())

    session.add(category)
    await session.commit()
    await session.refresh(category)

    return category


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))],
)
async def update_category(
    category_id: str, category_in: CategoryUpdate, session: SessionDep
):
    result = await session.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    for field, value in category_in.model_dump(exclude_unset=True).items():
        setattr(category, field, value)

    await session.commit()
    await session.refresh(category)

    return category


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def delete_category(category_id: str, session: SessionDep):
    result = await session.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Category not found"
        )

    await session.delete(category)
    await session.commit()
