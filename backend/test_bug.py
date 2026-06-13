import asyncio
from sqlalchemy import select, or_, func
from app.models.others import Resource
from app.services.resource_scope import resource_scope_clause
from app.db.session import async_session_factory

async def main():
    async with async_session_factory() as db:
        course_ids = ["course1", "course2"]
        catalog_id = "feaef3b632bb4014"
        query = select(Resource).where(Resource.is_deleted == False)
        if course_ids:
            query = query.where(or_(*(resource_scope_clause(course_id, catalog_id) for course_id in course_ids)))
        else:
            query = query.where(Resource.catalog_id == catalog_id)
        
        # total
        stmt = select(func.count()).select_from(query.subquery())
        print(stmt)
        try:
            total = (await db.execute(stmt)).scalar() or 0
            print("total:", total)
        except Exception as e:
            print("ERROR:", e)

asyncio.run(main())
