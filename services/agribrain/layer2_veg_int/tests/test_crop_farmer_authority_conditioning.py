from services.agribrain.layer2_veg_int.crop_posterior import (
    infer_crop_posterior,
)


def _infer(authority: str) -> dict:
    return infer_crop_posterior(
        plot_id="plot-authority",
        run_id=f"run-{authority.lower()}",
        plot_timeseries=[],
        crop_config={
            "crop": "tomato",
            "crop_cycle_id": "cycle-authority",
            "declared_crop_authority": authority,
        },
        operational_context={},
        archive_context={},
    )


def test_authenticated_farmer_declaration_uses_confirmed_conditioning():
    farmer = _infer("FARMER_CONFIRMED")
    user = _infer("USER_CONFIRMED")

    assert farmer["authority"] == "FARMER_CONFIRMED"
    assert farmer["crop_group_posterior"] == user["crop_group_posterior"]
