import pytest
import asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from app.models.domain import User, Account
from app.db.seed import seed_simulator_data
from app.db.database import AsyncSessionLocal
from sqlalchemy.future import select

@pytest.mark.asyncio
async def test_records_persist_after_reconnecting(db_session):
    # Insert a user
    user = User(identity_provider_subject="reconnect-test")
    db_session.add(user)
    await db_session.commit()
    
    # Close session
    await db_session.close()
    
    # Open new session
    from sqlalchemy.ext.asyncio import async_sessionmaker
    TestingSessionLocal = async_sessionmaker(db_session.bind, expire_on_commit=False)
    async with TestingSessionLocal() as new_session:
        stmt = select(User).where(User.identity_provider_subject == "reconnect-test")
        result = await new_session.execute(stmt)
        fetched = result.scalar_one_or_none()
        assert fetched is not None
        assert fetched.identity_provider_subject == "reconnect-test"
        
        # Cleanup
        await new_session.delete(fetched)
        await new_session.commit()

@pytest.mark.asyncio
async def test_repeat_seeding_does_not_duplicate(db_session):
    # Run first time
    user1, account1 = await seed_simulator_data(db_session)
    
    # Run second time
    user2, account2 = await seed_simulator_data(db_session)
    
    assert user1.id == user2.id
    assert account1.id == account2.id
    
    # Verify count
    result = await db_session.execute(select(User).where(User.identity_provider_subject == "simulator-user-1"))
    users = result.scalars().all()
    assert len(users) == 1

@pytest.mark.asyncio
async def test_failed_transactions_rollback(db_session):
    # Start a logical block
    user = User(identity_provider_subject="valid-user")
    db_session.add(user)
    await db_session.flush() # Valid
    
    # Intentionally cause a failure (duplicate identity)
    duplicate_user = User(identity_provider_subject="valid-user")
    db_session.add(duplicate_user)
    
    try:
        await db_session.commit()
        pytest.fail("Should have raised IntegrityError")
    except IntegrityError:
        await db_session.rollback()
        
    # Verify first valid write was also rolled back
    result = await db_session.execute(select(User).where(User.identity_provider_subject == "valid-user"))
    assert result.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_unique_constraints_reject_duplicates(db_session):
    user1 = User(identity_provider_subject="unique-test")
    db_session.add(user1)
    await db_session.commit()
    
    user2 = User(identity_provider_subject="unique-test")
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

@pytest.mark.asyncio
async def test_database_outage_produces_honest_failure():
    # Intentionally use a bad port to simulate outage
    from tests.conftest import TEST_DATABASE_URL
    # Replace the port with an unreachable port to simulate a DB outage
    bad_engine = create_async_engine(TEST_DATABASE_URL.split("@")[0] + "@127.0.0.1:9999/tradeguard_test")
    
    with pytest.raises(Exception) as exc_info:
        async with bad_engine.connect() as conn:
            await conn.execute("SELECT 1")
            
    # The error should be a connection error, honest failure
    assert "Connect call failed" in str(exc_info.value) or "refused" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()
