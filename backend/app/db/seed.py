import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.domain import User, Account, AccountMembership

async def seed_simulator_data(session: AsyncSession):
    """
    Idempotent seeding function for the simulator.
    """
    # Create or get user
    stmt = select(User).where(User.identity_provider_subject == "simulator-user-1")
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(identity_provider_subject="simulator-user-1")
        session.add(user)
        await session.flush()
        
    # Create or get account
    stmt = select(Account).where(Account.broker_connection_ref == "SIM-001")
    result = await session.execute(stmt)
    account = result.scalar_one_or_none()
    
    if not account:
        account = Account(
            broker_connection_ref="SIM-001",
            mode="SIMULATOR",
            currency="INR",
            account_display_label="Test Simulator Account"
        )
        session.add(account)
        await session.flush()
        
    # Create or get membership
    stmt = select(AccountMembership).where(
        AccountMembership.account_id == account.id,
        AccountMembership.user_id == user.id
    )
    result = await session.execute(stmt)
    membership = result.scalar_one_or_none()
    
    if not membership:
        membership = AccountMembership(
            account_id=account.id,
            user_id=user.id,
            role="TRADER"
        )
        session.add(membership)
        
    await session.commit()
    return user, account
