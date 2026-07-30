"""
Archive configuration limits and thresholds.
"""
import os

# Storage and scene limits
ARCHIVE_MAX_SCENES_PER_PLOT = int(os.environ.get("AGRIWISE_ARCHIVE_MAX_SCENES_PER_PLOT", "500"))
ARCHIVE_MAX_STORAGE_MB_PER_PLOT = 2048
ARCHIVE_MAX_DOWNLOAD_MB_PER_JOB = 512
ARCHIVE_DEFAULT_MODE = "seasonal"
ARCHIVE_FULL_MODE_REQUIRES_ADMIN = True

# Sentinel-1 incidence angle policy
S1_INC_ANGLE_MIN_DEG = 20.0
S1_INC_ANGLE_MAX_DEG = 50.0
S1_INC_ANGLE_POLICY_VERSION = "v90_7_s1_incidence_policy_v1"

# In-memory OAuth config
CDSE_AUTH_MODE = "client_credentials"
