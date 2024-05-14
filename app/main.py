import os
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

JWT_SECRET = os.getenv("JWT_SECRET")

security = HTTPBearer()

app = FastAPI(title="Otter Point")

# TODO: allow_origins
app.add_middleware(
    CORSMiddleware,
    # allow_origins="*",
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


pool = AsyncConnectionPool(open=False)


async def get_db_conn():
    if pool.closed:
        await pool.open()
    async with pool.connection() as conn:
        yield conn


def get_user_wallet_address(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    return payload["walletAddress"]


@app.get("/", summary="Check health.", description="Check health.")
async def root():
    return {}


# WalletVaultSnapshot cte
wallet_vault_snapshot_cte = """
WITH "WalletVaultSnapshot" AS (
    SELECT
        wvs.*,
        vsb.*
    FROM public."WalletVaultSnapshot" wvs
    JOIN public."VaultSnapshotBlock" vsb ON wvs."vaultSnapshotBlockId" = vsb.id
)
"""


@app.get("/otter-point", summary="Get otter point.", description="Get otter point.")
async def get_otter_point(
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
    # wallet_address: Annotated[str, Depends(get_user_wallet_address)],
):
    wallet_address = "0x41a539B1b75962d01C874ec6f960FCf57C41bD58"

    cur = conn.cursor()

    await cur.execute(
        """
        SELECT "ReferrerUser"."walletAddress"
        FROM "Referral"
        JOIN "User" AS "RefereeUser" ON "Referral"."refereeUserId" = "RefereeUser".id
        JOIN "User" AS "ReferrerUser" ON "Referral"."referrerUserId" = "ReferrerUser".id
        WHERE "RefereeUser"."walletAddress" = %s
        """,
        (wallet_address,),
    )
    row = await cur.fetchone()
    referrer_wallet_address = row[0] if row else None

    await cur.execute(
        f"""
        {wallet_vault_snapshot_cte}
        SELECT SUM(amount * rate / 1000000000000000000 * price / 100000000)
        FROM "WalletVaultSnapshot"
        WHERE "WalletVaultSnapshot"."address" = %s
        """,
        (wallet_address,),
    )
    row = await cur.fetchone()
    earned_amount = row[0] if row else 0

    referral_amount = 0

    await cur.execute(
        """
        SELECT
            SUM(wvs.amount * vsb.rate / 1000000000000000000 * vsb.price / 100000000)
        FROM "User"
        JOIN "Referral" ON "User".id = "Referral"."referrerUserId"
        JOIN "User" AS "RefereeUser" ON "Referral"."refereeUserId" = "RefereeUser".id
        JOIN "WalletVaultSnapshot" AS wvs ON "RefereeUser"."walletAddress" = wvs."address"
        JOIN "VaultSnapshotBlock" AS vsb ON wvs."vaultSnapshotBlockId" = vsb.id
        JOIN "SnapshotBlock" AS sb ON vsb."snapshotBlockId" = sb.id
        WHERE "User"."walletAddress" = %s AND sb."timestamp" >= "Referral"."createdAt"
        """,
        (wallet_address,),
    )
    row = await cur.fetchone()
    referral_amount = row[0] if row else 0

    total_amount = earned_amount + referral_amount

    return {
        "referral_code": referrer_wallet_address,
        "earned_amount": earned_amount,
        "referral_amount": referral_amount,
        "total_amount": total_amount,
    }


class SetReferralCodeBody(BaseModel):
    referral_code: str


@app.post(
    "/otter-point/referral",
    summary="Set referral code.",
    description="Set referral code.",
)
async def set_referral_code(
    conn: Annotated[AsyncConnection, Depends(get_db_conn)],
    wallet_address: Annotated[str, Depends(get_user_wallet_address)],
    body: SetReferralCodeBody,
):
    cur = conn.cursor()
    await cur.execute(
        'SELECT id FROM "User" WHERE "walletAddress" = %s', (body.referral_code,)
    )
    referrer_user_id = (await cur.fetchone())[0]
    if not referrer_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    await cur.execute(
        'SELECT id FROM "User" WHERE "walletAddress" = %s', (wallet_address,)
    )
    referee_user_id = (await cur.fetchone())[0]
    if not referee_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    await cur.execute(
        'INSERT INTO "Referral" ("referrerUserId", "refereeUserId") VALUES (%s, %s)',
        (referrer_user_id, referee_user_id),
    )

    return {}
