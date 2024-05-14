
CREATE TABLE public."Vault" (
  id SERIAL PRIMARY KEY,
  name text NOT NULL,
  address text NOT NULL,
  "oracleAddress" text NOT NULL,
  "blockNumber" int NOT NULL
);

-- INSERT INTO public."Vault" (id, name, address, oracleAddress, snapshotBlockNumber, snapshotAt) VALUES (1, 'AAVE USDC', '0x7100409BaAEDa121aB92f663e3Ddb898F11Ff745', '0x43d12Fb3AfCAd5347fA764EeAB105478337b7200', 3643052, '2024-02-26 07:27:12');
-- INSERT INTO public."Vault" (id, name, address, oracleAddress, snapshotBlockNumber, snapshotAt) VALUES (2, 'AAVE ETH', '0x844Ccc93888CAeBbAd91332FCa1045e6926a084d', '0x6bF14CB0A831078629D993FDeBcB182b21A8774C', 3861566, '2021-05-05 06:30:40');

CREATE TABLE public."SnapshotBlock" (
    id SERIAL PRIMARY KEY,
    "blockNumber" int NOT NULL,
    timestamp timestamp(0) without time zone NOT NULL
);

CREATE TABLE public."VaultSnapshotBlock" (
    id SERIAL PRIMARY KEY,
    "vaultId" integer NOT NULL REFERENCES "Vault" (id) ON DELETE CASCADE,
    rate numeric NOT NULL,
    price numeric NOT NULL,
    "snapshotBlockId" integer NOT NULL REFERENCES "SnapshotBlock" (id) ON DELETE CASCADE
);

CREATE TABLE public."WalletVaultSnapshot" (
    id integer NOT NULL,
    address text NOT NULL,
    amount numeric NOT NULL
    "VaultSnapshotBlockId" integer NOT NULL REFERENCES "VaultSnapshotBlock" (id) ON DELETE CASCADE
);

CREATE TABLE public."User" (
    id integer NOT NULL,
    "walletAddress" text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);

CREATE TABLE public."Referral" (
    id integer NOT NULL,
    "referrerUserId" integer NOT NULL,
    "refereeUserId" integer NOT NULL,
    "createdAt" timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


