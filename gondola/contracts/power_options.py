"""Optional supply boards; their mechanical provision is not power qualification.

One BEC12S-PRO has one selectable output. Exact 8 V main and 5.2 V servo
rails require two regulators, not two connections to the same module.
Published body heights exclude unmeasured solder, headers, plugs and insulation.
"""

from collections import Counter
from dataclasses import asdict, dataclass

POWER_ARTIFACT_NAMES = (
    "gondola_power_options.FCStd",
    "optional_power_mount.stl",
    "optional_power_mount.step",
    "gondola_power_options.json",
)
POWER_VALIDATION_NAME = "gondola_power_validation.json"


@dataclass(frozen=True)
class PowerModuleProfile:
    key: str
    model: str
    size_mm: tuple[float, float, float]
    mass_g: float
    input_voltage_v: tuple[float, float]
    output_choices_v: tuple[float, ...]
    default_output_v: float
    published_continuous_current_a: float
    published_peak_current_a: float
    terminal_pitch_mm: float
    terminal_axes: tuple[str, ...]
    source: str
    dimension_source: str

    def contract(self):
        return {
            **asdict(self),
            "independent_output_channels": 1,
            "mounting_hole_centres_mm": (),
            "mounting_hole_diameter_mm": None,
            "dimension_scope": "Published long-side X, width Y and bare-module Z envelope. Terminal axes are conservative end-band orientations in that normalized frame, not measured solder-pad or header XYZ. Fitted headers, plugs, solder, insulation and compliant support add unmeasured height.",
            "attachment": "Use the common insulating support with adhesive/ties clear of hot components and terminals. The visible electrical plated holes are not mounting holes. No board-specific screw pattern is inferred.",
            "electrical_scope": "One selectable output per board. Catalog current is not an installed thermal limit or validated load budget. Verify polarity, output selection and voltage before connecting equipment; these modules have no reverse-input protection.",
            "thermal_scope": "Keep the populated side exposed to cooling air and inspect the received underside before applying insulation or adhesive. No installation-specific derating, touch temperature or adhesive temperature qualification is available.",
            "retention_verified": False,
            "installed_port_datums_verified": False,
            "installed_load_and_thermal_verified": False,
        }


POWER_MODULE_PROFILES = {
    "BEC12S_PRO": PowerModuleProfile(
        key="BEC12S_PRO",
        model="MATEK BEC12S-PRO",
        size_mm=(35.0, 24.0, 5.5),
        mass_g=5.0,
        input_voltage_v=(9.0, 55.0),
        output_choices_v=(5.2, 8.0, 12.0),
        default_output_v=5.2,
        published_continuous_current_a=5.0,
        published_peak_current_a=9.0,
        terminal_pitch_mm=3.81,
        terminal_axes=("-X",),
        source="https://www.mateksys.com/?portfolio=bec12s-pro",
        dimension_source="https://www.mateksys.com/wp-content/uploads/2022/10/BEC12S-PRO_1.jpg",
    ),
    "SVPDB_8S": PowerModuleProfile(
        key="SVPDB_8S",
        model="MATEK SVPDB-8S",
        size_mm=(26.0, 21.0, 5.0),
        mass_g=4.0,
        input_voltage_v=(5.5, 36.0),
        output_choices_v=(5.0, 6.0, 7.2, 8.2),
        default_output_v=5.0,
        published_continuous_current_a=4.0,
        published_peak_current_a=7.0,
        terminal_pitch_mm=2.54,
        terminal_axes=("-X", "+X"),
        source="https://www.mateksys.com/?portfolio=svpdb-8s",
        dimension_source="https://www.mateksys.com/wp-content/uploads/2022/07/SVPDB-8S_1.jpg",
    ),
}


@dataclass(frozen=True)
class RegulatorBranch:
    module_key: str
    output_voltage_v: float
    load: str


@dataclass(frozen=True)
class PowerPlan:
    key: str
    source: str
    nominal_input_voltage_v: float
    branches: tuple[RegulatorBranch, ...]

    def contract(self):
        counts = Counter(branch.module_key for branch in self.branches)
        return {
            **asdict(self),
            "regulator_quantities": dict(counts),
            "listed_regulator_mass_g": sum(
                POWER_MODULE_PROFILES[key].mass_g * count
                for key, count in counts.items()
            ),
            "branch_topology": "Each listed regulator receives the source directly; listed outputs are separate positive rails with common ground. No output paralleling or regulator cascade is specified.",
            "qualification": "Optional integration plan only. Board fit does not establish motor/startup current, tether loss, protection, cooling, FC input compatibility or a completed wiring harness.",
        }


POWER_PLANS = {
    "BATTERY": PowerPlan("BATTERY", "Existing standard 2S LiPo", 7.4, ()),
    "TETHER_DUAL_BEC": PowerPlan(
        "TETHER_DUAL_BEC",
        "External 24 V DC PSU",
        24.0,
        (
            RegulatorBranch("BEC12S_PRO", 8.0, "FC VBAT and propulsion"),
            RegulatorBranch("BEC12S_PRO", 5.2, "Servo positive rail only"),
        ),
    ),
    "TETHER_BEC_SVPDB": PowerPlan(
        "TETHER_BEC_SVPDB",
        "External 24 V DC PSU",
        24.0,
        (
            RegulatorBranch("BEC12S_PRO", 8.0, "FC VBAT and propulsion"),
            RegulatorBranch("SVPDB_8S", 5.0, "Servo positive rail only"),
        ),
    ),
    "BATTERY_SVPDB": PowerPlan(
        "BATTERY_SVPDB",
        "Existing standard 2S LiPo",
        7.4,
        (RegulatorBranch("SVPDB_8S", 5.0, "Servo positive rail only"),),
    ),
}
SELECTED_POWER_PLAN_KEY = "BATTERY"


def get_power_module_profile(key):
    try:
        return POWER_MODULE_PROFILES[key]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Unsupported power module: {key!r}") from error


def get_power_plan(key=None):
    key = SELECTED_POWER_PLAN_KEY if key is None else key
    try:
        return POWER_PLANS[key]
    except (KeyError, TypeError) as error:
        raise ValueError(f"Unsupported power plan: {key!r}") from error


def power_option_contract():
    return {
        "selected_plan": get_power_plan().contract(),
        "modules": {
            key: profile.contract() for key, profile in POWER_MODULE_PROFILES.items()
        },
        "optional_plans": {key: plan.contract() for key, plan in POWER_PLANS.items()},
        "connection_limits": (
            "A BEC12S-PRO cannot produce 8 V and 5.2 V simultaneously; exact dual rails use two separate modules fed from 24 V in parallel.",
            "SVPDB-8S offers 5, 6, 7.2 or 8.2 V, not 5.2 V. The optional SVPDB servo plan deliberately uses its default 5 V setting.",
            "Keep servo-positive wires off the FC 5 V rail when using an external servo regulator. Share ground and preserve separate control signals. Do not feed the LR24-F-Mini or other 5 V peripherals from the 5.2 V servo rail.",
            "Battery and tether are mutually exclusive supply choices here; no automatic changeover, charging or parallel battery/PSU operation is designed.",
            "The selected FC's published input-range conflict is unresolved for both existing 2S operation and an 8 V tether output. Preserve the selected board, but do not claim those supply combinations qualified.",
            "Tether guidance supports local routing and strain relief only. It does not establish whole-tether load capacity, cable rating, loss, anchor retention or freedom from all propeller/optical interference during flight.",
        ),
    }
