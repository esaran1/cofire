"""Runtime configuration. Every path and date range is overridable by env."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Census-published extents (not invented). Used only if TIGER fetch fails.
COLORADO_BBOX: tuple[float, float, float, float] = (-109.06, 36.99, -102.04, 41.00)
COLORADO_BBOX_BUFFERED: tuple[float, float, float, float] = (-109.56, 36.49, -101.54, 41.50)
LARIMER_BBOX: tuple[float, float, float, float] = (-106.192, 40.324, -104.943, 40.998)
LARIMER_FIPS = "08069"
# Pueblo County: the Larimer-sized southern domain with the most in-domain 2026
# perimeter area (109,408 acres over 2 fires, including Aspen Acres at 102,003 ac,
# the largest Colorado perimeter of 2026). 484 cells against Larimer's 494, so
# runtimes stay comparable. Larimer contains 0 in-domain 2026 perimeters, which
# left the fire evaluation empty through v0.5.
PUEBLO_BBOX: tuple[float, float, float, float] = (-105.051, 37.735, -104.054, 38.522)
PUEBLO_FIPS = "08101"
COLORADO_FIPS = "08"

SUBSETS: dict[str, tuple[tuple[float, float, float, float], str]] = {
    "larimer": (LARIMER_BBOX, LARIMER_FIPS),
    "pueblo": (PUEBLO_BBOX, PUEBLO_FIPS),
}

HORIZONS_WEEKS: tuple[int, int, int] = (2, 4, 8)
COVERAGE_TARGET = 0.90
ACI_LR = 0.01
SEED = 2026


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="COFIRE_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    dev_subset: bool = True
    # Which dev subset to use when dev_subset=1. COFIRE_SUBSET_NAME=larimer|pueblo.
    # Pueblo is the default from v0.6: Larimer has 0 in-domain 2026 perimeters.
    subset_name: str = "pueblo"
    data_dir: Path = Path("data")
    artifacts_dir: Path = Path("artifacts")
    log_dir: Path = Path("logs")
    seed: int = SEED

    database_url: str = Field(default="sqlite:///data/cofire.db", alias="DATABASE_URL")

    synoptic_token: str = Field(default="", alias="SYNOPTIC_TOKEN")
    earthdata_username: str = Field(default="", alias="EARTHDATA_USERNAME")
    earthdata_password: str = Field(default="", alias="EARTHDATA_PASSWORD")

    enable_nfmd: bool = False
    enable_raws: bool = False
    enable_smap: bool = False
    enable_hrrr: bool = False
    enable_hls: bool = False
    lambda_hydro: float = 0.1
    lambda_fuel: float = 0.1
    bootstrap_samples: int = 300
    external_drought_nc: Path = Path("data/external/drought_pred.nc")

    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # 2007 because USDM reaches 2007 and no further. ERC goes back to 2004, but
    # a drought target cannot be built without its label. Kept identical to the
    # value `apply_subset_defaults` sets, so a bare `Settings()` and a
    # `get_settings()` cannot disagree about the split: analysis code
    # constructs both, and a silent split difference between the calibration
    # path and the evaluation path is exactly the class of bug that produced
    # the original ACI failure.
    train_start: date = date(2007, 1, 1)
    train_end: date = date(2021, 12, 31)
    valid_start: date = date(2022, 1, 1)
    valid_end: date = date(2023, 12, 31)
    calibrate_start: date = date(2024, 1, 1)
    calibrate_end: date = date(2025, 12, 31)
    hindcast_start: date = date(2026, 1, 6)
    # Inclusive data window for labels; latest USDM is discovered at fetch time.
    data_end: date = date(2026, 9, 15)
    warmup_days: int = 365

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        if self.dev_subset:
            return SUBSETS[self.subset_name][0]
        return COLORADO_BBOX_BUFFERED

    @property
    def county_fips(self) -> str | None:
        return SUBSETS[self.subset_name][1] if self.dev_subset else None

    def apply_subset_defaults(self) -> None:
        """Remap date splits when running a dev subset.

        The extended record restores the full split. This override previously
        forced train 2019 to 2022, which left a *two-year* effective training
        window once the LODO folds were carved out, and that thinness was what
        the 2007 back-extension exists to fix.

        The start is 2007 because USDM reaches 2007 and no further: ERC goes
        back to 2004, but a drought target cannot be built without its label.
        """
        if not self.dev_subset:
            return
        self.train_start = date(2007, 1, 1)
        self.train_end = date(2021, 12, 31)
        self.valid_start = date(2022, 1, 1)
        self.valid_end = date(2023, 12, 31)
        self.calibrate_start = date(2024, 1, 1)
        self.calibrate_end = date(2025, 12, 31)
        self.hindcast_start = date(2026, 1, 6)

    @property
    def fetch_start(self) -> date:
        return date.fromordinal(self.train_start.toordinal() - self.warmup_days)

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        """Subset-scoped so two dev subsets can coexist on disk.

        Larimer data predates this split and lives at the unscoped path, which is
        kept as the `larimer` location so v0.5 artifacts stay reproducible. A new
        subset gets `processed_<name>/`, so fetching Pueblo cannot clobber
        Larimer and the two domains can be compared.
        """
        if self.dev_subset and self.subset_name != "larimer":
            return self.data_dir / f"processed_{self.subset_name}"
        return self.data_dir / "processed"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.apply_subset_defaults()
    for path in (
        settings.data_dir,
        settings.raw_dir,
        settings.processed_dir,
        settings.cache_dir,
        settings.artifacts_dir,
        settings.log_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return settings
