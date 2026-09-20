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
COLORADO_FIPS = "08"

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

    train_start: date = date(2004, 1, 1)
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
            return LARIMER_BBOX
        return COLORADO_BBOX_BUFFERED

    @property
    def county_fips(self) -> str | None:
        return LARIMER_FIPS if self.dev_subset else None

    def apply_subset_defaults(self) -> None:
        """Remap date splits when running the Larimer vertical slice."""
        if not self.dev_subset:
            return
        self.train_start = date(2019, 1, 1)
        self.train_end = date(2022, 12, 31)
        self.valid_start = date(2023, 1, 1)
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
