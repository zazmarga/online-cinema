from datetime import date
from typing import Optional, List

from fastapi_filter.contrib.sqlalchemy import Filter
from pydantic import Field

from src.database.models.payments import PaymentStatusEnum, PaymentModel


class PaymentFilter(Filter):
    user_id__in: Optional[List[int]] = Field(
        None,
        alias="UserIdInList",
        description="Filter payments by user_id/list(user_id), ex.: 2,3",
    )
    created_at__gte: Optional[date] = Field(
        None,
        alias="DataStartDate",
        description="Filter payments by start date (inclusive), ex.: YYYY-MM-DD",
    )
    created_at__lte: Optional[date] = Field(
        None,
        alias="DataEndDate",
        description="Filter payments by end date (inclusive), ex.: YYYY-MM-DD",
    )
    status__in: Optional[List[PaymentStatusEnum]] = Field(
        None, alias="Status", description="Filter payments by status, ex.: successful"
    )

    class Config:
        populate_by_name = True

    class Constants(Filter.Constants):
        model = PaymentModel


def normalize_search_list(search_list: List[str]) -> List[str]:
    return [item.title() for item in search_list]
