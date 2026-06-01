import logging
import sys

# Gravity Constants
MU = 398600.4418
J2 = 1.08263e-3
RE_KM = 6378.137

# Earth rotation rate (rad/s)
OMEGA_EARTH = [0, 0, 7.292115e-5]

def get_logger(name: str) -> logging.Logger:
    """Configures and returns a standard logger for the project."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger
