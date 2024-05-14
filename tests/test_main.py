import os

import jwt
import pytest
from httpx import AsyncClient
from psycopg import AsyncConnection

JWT_SECRET = os.getenv("JWT_SECRET")


@pytest.mark.anyio
async def test_otter_point(client: AsyncClient, conn: AsyncConnection):

    cur = conn.cursor()

    await cur.execute(
        'INSERT INTO "User" ("walletAddress", "updatedAt") VALUES (\'0x111\', CURRENT_TIMESTAMP) RETURNING id'
    )
    referrer_user_id = (await cur.fetchone())[0]

    await cur.execute(
        'INSERT INTO "User" ("walletAddress", "updatedAt") VALUES (\'0x222\', CURRENT_TIMESTAMP) RETURNING id'
    )
    referee_user_id = (await cur.fetchone())[0]

    token = jwt.encode({"walletAddress": "0x222"}, JWT_SECRET, algorithm="HS256")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/otter-point/referral", headers=headers, json={"referral_code": "0x111"}
    )
    assert response.status_code == 200, response.text

    response = await client.get("/otter-point", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["referral_code"] == "0x111"
