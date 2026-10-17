from decimal import Decimal
from .schemas import Scenario


def calculate(scenario: Scenario) -> dict:
    p, f, w, r = (Decimal(str(x)) for x in (scenario.it_capacity_mw, scenario.load_factor, scenario.wue_l_per_kwh, scenario.reclaimed_share))
    energy = p * 1000 * f * 8760
    water = energy * w / 1000
    fresh = water * (1-r)
    return {
        'it_energy_kwh': float(energy),
        'onsite_water_m3': float(water),
        'freshwater_m3': float(fresh),
        'reclaimed_water_m3': float(water-fresh),
        'freshwater_mld': float(fresh / 365 / 1000),
    }


def compare_scenarios(baseline: Scenario, alternative: Scenario) -> dict:
    b, a = calculate(baseline), calculate(alternative)
    delta = Decimal(str(b['freshwater_m3'])) - Decimal(str(a['freshwater_m3']))
    percent = float(delta / Decimal(str(b['freshwater_m3'])) * 100) if b['freshwater_m3'] else None
    return {'baseline': b, 'alternative': a, 'reduction_m3': float(delta), 'reduction_percent': percent}
