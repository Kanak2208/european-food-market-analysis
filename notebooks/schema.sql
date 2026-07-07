-- ============================================================================
-- schema.sql · Normalized database schema (MySQL)
-- European Packaged-Food Market Analysis — Open Food Facts capstone
--
-- Design: a small star-style schema.
--   countries          (dimension)  — one row per market + economic attributes
--   nutriscore_grades  (lookup)     — A–E grade -> rank + label
--   products           (entity)     — one row per unique barcode
--   product_markets    (bridge)     — many-to-many: which markets sell each product
--
-- Load order matters (foreign keys): countries & nutriscore_grades first,
-- then products, then product_markets.
-- ============================================================================

-- Drop in reverse-dependency order so re-running is clean
DROP TABLE IF EXISTS product_markets;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS nutriscore_grades;
DROP TABLE IF EXISTS countries;

-- ----------------------------------------------------------------------------
-- 1. COUNTRIES — dimension table (the 10 largest European economies)
--    GDP figures: IMF World Economic Outlook (April 2026), 2025 nominal estimate.
--    gdp_rank_europe is the rank among ALL European countries (hence the gaps:
--    #4 Russia and #11 Ireland are not part of this study).
-- ----------------------------------------------------------------------------
CREATE TABLE countries (
    country            VARCHAR(50)   NOT NULL,
    country_tag        VARCHAR(50)   NOT NULL,   -- Open Food Facts tag, e.g. en:germany
    gdp_usd_billion    DECIMAL(10,1) NOT NULL,   -- 2025 nominal GDP, billions USD
    gdp_rank_europe    TINYINT       NOT NULL,   -- rank within Europe
    gdp_per_capita_usd INT           NOT NULL,   -- 2025 nominal GDP per capita, USD
    gdp_year           SMALLINT      NOT NULL,
    PRIMARY KEY (country)
);

INSERT INTO countries (country, country_tag, gdp_usd_billion, gdp_rank_europe, gdp_per_capita_usd, gdp_year) VALUES
    ('Germany',        'en:germany',         5048.1,  1,  60439, 2025),
    ('United Kingdom', 'en:united-kingdom',  4003.0,  2,  57608, 2025),
    ('France',         'en:france',          3368.9,  3,  48930, 2025),
    ('Italy',          'en:italy',           2550.1,  5,  43270, 2025),
    ('Spain',          'en:spain',           1903.8,  6,  38290, 2025),
    ('Netherlands',    'en:netherlands',     1332.2,  7,  73833, 2025),
    ('Switzerland',    'en:switzerland',     1043.5,  8, 115620, 2025),
    ('Poland',         'en:poland',          1035.6,  9,  28374, 2025),
    ('Belgium',        'en:belgium',          724.9, 10,  61002, 2025),
    ('Sweden',         'en:sweden',           669.0, 12,  62662, 2025);

-- ----------------------------------------------------------------------------
-- 2. NUTRISCORE_GRADES — lookup table (grade -> rank + human label)
--    grade_rank: 1 = healthiest ... 5 = least healthy (lets you AVG/ORDER grades)
-- ----------------------------------------------------------------------------
CREATE TABLE nutriscore_grades (
    grade       CHAR(1)     NOT NULL,
    grade_rank  TINYINT     NOT NULL,
    description VARCHAR(40) NOT NULL,
    PRIMARY KEY (grade)
);

INSERT INTO nutriscore_grades (grade, grade_rank, description) VALUES
    ('A', 1, 'Healthiest'),
    ('B', 2, 'Good'),
    ('C', 3, 'Moderate'),
    ('D', 4, 'Poor'),
    ('E', 5, 'Least healthy');

-- ----------------------------------------------------------------------------
-- 3. PRODUCTS — entity table (one row per unique barcode)
--    Nutrition facts are intrinsic to the product, so they live here, NOT
--    repeated per country. nutriscore_grade may be NULL (unknown) — that's
--    allowed and does not violate the foreign key.
-- ----------------------------------------------------------------------------
CREATE TABLE products (
    code               VARCHAR(50)   NOT NULL,
    product_name       VARCHAR(255),
    brands             VARCHAR(255),
    nutriscore_grade   CHAR(1),
    nutriscore_score   SMALLINT,
    nova_group         TINYINT,
    eco_grade          VARCHAR(20),
    additives_n        SMALLINT,
    energy_kcal_100g   DECIMAL(7,2),
    sugars_100g        DECIMAL(6,2),
    fat_100g           DECIMAL(6,2),
    saturated_fat_100g DECIMAL(6,2),
    salt_100g          DECIMAL(7,3),
    sodium_100g        DECIMAL(7,3),
    proteins_100g      DECIMAL(6,2),
    fiber_100g         DECIMAL(6,2),
    completeness       DECIMAL(4,3),
    last_modified      DATETIME,
    PRIMARY KEY (code),
    CONSTRAINT fk_products_grade
        FOREIGN KEY (nutriscore_grade) REFERENCES nutriscore_grades (grade)
);

-- ----------------------------------------------------------------------------
-- 4. PRODUCT_MARKETS — bridge table (many-to-many product <-> country)
--    One row per (product, market). This is the ~70k-row fact table.
-- ----------------------------------------------------------------------------
CREATE TABLE product_markets (
    code    VARCHAR(50) NOT NULL,
    country VARCHAR(50) NOT NULL,
    PRIMARY KEY (code, country),
    CONSTRAINT fk_pm_product FOREIGN KEY (code)    REFERENCES products (code),
    CONSTRAINT fk_pm_country FOREIGN KEY (country) REFERENCES countries (country)
);
