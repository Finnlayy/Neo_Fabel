import asyncio

from sqlalchemy import text

from backend.app.database import SessionFactory


async def main() -> None:
    async with SessionFactory() as session:
        await session.execute(
            text(
                "UPDATE signal_routes SET mode = 'bypass_ai' "
                "WHERE strategy_id IN ('fable_dca_default', 'fable_grid_default')"
            )
        )
        await session.commit()
        rows = (
            await session.execute(text("SELECT strategy_id, mode, enabled FROM signal_routes"))
        ).all()
        print("routes:", rows)


if __name__ == "__main__":
    asyncio.run(main())
