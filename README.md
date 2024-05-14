pg_dump -f temp.sql --no-owner --no-acl
docker-compose up db -d
psql -f db/init.sql

add Vault.blockNumber
add Referral.createdAt
