"""
Results Router — /results
==========================
Admin-only aggregated results. Never returns raw voter data.
CSV export for offline use.
"""

import csv
import io

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.routers.deps import AdminDep
from app.services import content_service

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/")
async def get_all_results(admin: AdminDep):
    """Return aggregated vote counts per nominee per category. Admin only."""
    results = await content_service.get_all_results()
    return results


@router.get("/{category_id}")
async def get_category_results(admin: AdminDep, category_id: str):
    """Return aggregated results for a single category."""
    cat = await content_service.get_category(category_id)
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    results = await content_service.get_results(category_id)
    return {
        "category_id": category_id,
        "category_name": cat.name,
        "category_type": cat.type,
        "results": results,
    }


@router.get("/export/csv")
async def export_results_csv(admin: AdminDep):
    """Export all results as a CSV file. Columns: category, nominee, vote_count, winner."""
    all_results = await content_service.get_all_results()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["category_name", "category_type", "nominee_name", "vote_count", "is_winner"])

    for cat_result in all_results:
        for entry in cat_result.get("results", []):
            writer.writerow([
                cat_result["category_name"],
                cat_result["category_type"],
                entry["nominee_name"],
                entry["vote_count"],
                "Yes" if entry["is_winner"] else "No",
            ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=premed_results.csv"},
    )
