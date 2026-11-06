from datetime import date as DateType

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import UserMixin

class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


class User( UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(
        String(254),
        unique=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="user",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Expense(db.Model):
    __tablename__ = "expenses"

    __table_args__ = (
        CheckConstraint(
            "amount_kobo > 0",
            name="expense_amount_positive",
        ),
        CheckConstraint(
            "length(trim(category)) > 0",
            name="expense_category_not_blank",
        ),
        CheckConstraint(
            "length(trim(item)) > 0",
            name="expense_item_not_blank",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    date: Mapped[DateType] = mapped_column(nullable=False)

    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    item: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    amount_kobo: Mapped[int] = mapped_column(nullable=False)

    user: Mapped["User"] = relationship(
        back_populates="expenses",
    )