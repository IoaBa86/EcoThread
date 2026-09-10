from core.energy_calculator import EnergyCalculator, format_energy, format_energy_auto


def make_calculator(**overrides):
    kwargs = dict(
        package_tdp_watts=60.0,
        idle_baseline_watts=5.0,
        carbon_intensity_g_per_kwh=400.0,
        electricity_price_per_kwh=0.20,
        logical_core_count=4,
    )
    kwargs.update(overrides)
    return EnergyCalculator(**kwargs)


def test_estimate_watts_at_zero_cpu_returns_idle_baseline():
    calc = make_calculator()
    assert calc.estimate_watts(0.0) == 5.0


def test_estimate_watts_at_full_single_core_load_is_between_idle_and_max():
    calc = make_calculator()
    # 100% on one of 4 cores -> core_fraction 0.25, non-zero but under full TDP.
    watts = calc.estimate_watts(100.0)
    assert 5.0 < watts < 65.0


def test_estimate_watts_saturates_at_full_tdp_when_fully_loaded():
    calc = make_calculator()
    # cpu_percent can exceed 100 * core_count in psutil terms; the fraction
    # must clamp to 1.0 rather than overshoot idle + tdp.
    watts_at_max = calc.estimate_watts(400.0)  # 100% * 4 cores
    watts_over_max = calc.estimate_watts(999.0)
    assert watts_at_max == watts_over_max
    assert watts_at_max == 5.0 + 60.0


def test_estimate_watts_normalized_matches_estimate_watts_for_single_core():
    calc = make_calculator(logical_core_count=1)
    assert calc.estimate_watts(50.0) == calc.estimate_watts_normalized(0.5)


def test_accumulate_integrates_watts_over_elapsed_time(monkeypatch):
    calc = make_calculator()
    times = iter([100.0, 101.0, 103.0])  # first call primes, then +1s, then +2s
    monkeypatch.setattr("core.energy_calculator.time.monotonic", lambda: next(times))

    first = calc.accumulate(10.0)
    assert first == 0.0  # first call only primes the clock, no elapsed time yet

    second = calc.accumulate(10.0)  # 1s at 10W
    assert second == 10.0

    third = calc.accumulate(20.0)  # +2s at 20W
    assert third == 10.0 + 40.0


def test_reset_clears_accumulated_energy(monkeypatch):
    calc = make_calculator()
    times = iter([0.0, 1.0])
    monkeypatch.setattr("core.energy_calculator.time.monotonic", lambda: next(times))
    calc.accumulate(10.0)
    calc.accumulate(10.0)
    assert calc._total_joules > 0

    calc.reset()
    assert calc._total_joules == 0.0


def test_drop_last_sample_time_prevents_paused_duration_from_being_billed(monkeypatch):
    calc = make_calculator()
    times = iter([0.0, 1.0])
    monkeypatch.setattr("core.energy_calculator.time.monotonic", lambda: next(times))
    calc.accumulate(10.0)
    calc.accumulate(10.0)
    joules_before_pause = calc._total_joules

    calc.drop_last_sample_time()

    # Simulate a long real-world pause: the next accumulate() call should not
    # bill the gap as active wattage, because drop_last_sample_time() reset
    # the reference point.
    times_after_resume = iter([1000.0])
    monkeypatch.setattr("core.energy_calculator.time.monotonic", lambda: next(times_after_resume))
    joules_after_resume = calc.accumulate(10.0)
    assert joules_after_resume == joules_before_pause


def test_total_carbon_grams_scales_with_carbon_intensity(monkeypatch):
    calc = make_calculator(carbon_intensity_g_per_kwh=500.0)
    times = iter([0.0, 3600.0])  # exactly one hour
    monkeypatch.setattr("core.energy_calculator.time.monotonic", lambda: next(times))
    calc.accumulate(1000.0)  # priming call
    calc.accumulate(1000.0)  # 1000W for 1 hour = 1 kWh
    assert calc.total_carbon_grams() == 500.0


def test_total_cost_scales_with_price(monkeypatch):
    calc = make_calculator(electricity_price_per_kwh=0.30)
    times = iter([0.0, 3600.0])
    monkeypatch.setattr("core.energy_calculator.time.monotonic", lambda: next(times))
    calc.accumulate(1000.0)
    calc.accumulate(1000.0)
    assert round(calc.total_cost(), 6) == 0.30


def test_format_energy_explicit_units():
    assert format_energy(3661.0, "J") == "3661.0 J"
    assert format_energy(3600.0, "Wh") == "1.0000 Wh"
    assert format_energy(3_600_000.0, "kWh") == "1.000000 kWh"


def test_format_energy_auto_scales_by_magnitude():
    assert format_energy_auto(500.0).endswith("J")
    assert format_energy_auto(500_000.0).endswith("Wh")
    assert format_energy_auto(5_000_000_000.0).endswith("kWh")
