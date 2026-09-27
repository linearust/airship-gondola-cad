"""Optional supply boards; their mechanical provision is not power qualification.

The tether option uses one BEC12S-PRO at 8 V, feeding the main input and
one SVPDB-8S at 5 V. All downstream loads share the upstream BEC capacity.
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
            "attachment": "Use the common insulating support with adhesive clear of hot components and terminals. The visible electrical plated holes are not mounting holes. No board-specific screw pattern is inferred.",
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
    upstream_branch_index: int | None = None


@dataclass(frozen=True)
class PowerPlan:
    key: str
    source: str
    nominal_input_voltage_v: float
    branches: tuple[RegulatorBranch, ...]

    def __post_init__(self):
        for index, branch in enumerate(self.branches):
            upstream = branch.upstream_branch_index
            if upstream is not None and (
                type(upstream) is not int or not 0 <= upstream < index
            ):
                raise ValueError("A regulator may only draw from an earlier branch")
            profile = POWER_MODULE_PROFILES[branch.module_key]
            input_v = self.branch_input_voltage_v(index)
            low, high = profile.input_voltage_v
            if not low <= input_v <= high:
                raise ValueError("Regulator input outside its published range")
            if branch.output_voltage_v not in profile.output_choices_v:
                raise ValueError("Unsupported regulator output setting")
            if branch.output_voltage_v >= input_v:
                raise ValueError("These plans require a stepped-down regulated output")

    def branch_input_voltage_v(self, index):
        upstream = self.branches[index].upstream_branch_index
        return (
            self.nominal_input_voltage_v
            if upstream is None
            else self.branches[upstream].output_voltage_v
        )

    def contract(self):
        counts = Counter(branch.module_key for branch in self.branches)
        return {
            **asdict(self),
            "branches": [
                {
                    **asdict(branch),
                    "input_voltage_v": self.branch_input_voltage_v(index),
                    "input_from": (
                        "source"
                        if branch.upstream_branch_index is None
                        else f"branch[{branch.upstream_branch_index}].output"
                    ),
                }
                for index, branch in enumerate(self.branches)
            ],
            "regulator_quantities": dict(counts),
            "listed_regulator_mass_g": sum(
                POWER_MODULE_PROFILES[key].mass_g * count
                for key, count in counts.items()
            ),
            "branch_topology": "Each branch input follows its explicit input_from/upstream_branch_index. The upstream output supplies its direct loads and every downstream regulator input. Different regulated output positives remain separate; grounds are common.",
            "current_limits": [
                {
                    "branch_index": index,
                    "published_continuous_output_current_a": POWER_MODULE_PROFILES[
                        branch.module_key
                    ].published_continuous_current_a,
                    "nominal_voltage_times_published_current_w": branch.output_voltage_v
                    * POWER_MODULE_PROFILES[
                        branch.module_key
                    ].published_continuous_current_a,
                    "downstream_branch_indices": [
                        child_index
                        for child_index, child in enumerate(self.branches)
                        if child.upstream_branch_index == index
                    ],
                    "scope": "Shared output limit for direct loads plus downstream input current, including conversion loss. Ratings at different rails do not add. Voltage times catalog current is not a qualified installed power budget; startup, transient and thermal margin remain unmeasured.",
                }
                for index, branch in enumerate(self.branches)
            ],
            "qualification": "Optional integration plan only. Board fit does not establish motor/startup current, tether loss, protection, cooling, FC input compatibility or a completed wiring harness.",
        }


POWER_PLANS = {
    "BATTERY": PowerPlan("BATTERY", "Existing standard 2S LiPo", 7.4, ()),
    "TETHER_BEC_SVPDB": PowerPlan(
        "TETHER_BEC_SVPDB",
        "External 24 V DC PSU",
        24.0,
        (
            RegulatorBranch("BEC12S_PRO", 8.0, "FC VBAT and propulsion; SVPDB input"),
            RegulatorBranch("SVPDB_8S", 5.0, "Servo positive rail only", 0),
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
DEFAULT_OPTIONAL_POWER_PLAN_KEY = "TETHER_BEC_SVPDB"
OPTIONAL_POWER_PLAN_KEYS = tuple(
    key for key, plan in POWER_PLANS.items() if plan.branches
)


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
        "default_optional_plan": DEFAULT_OPTIONAL_POWER_PLAN_KEY,
        "modules": {
            key: profile.contract() for key, profile in POWER_MODULE_PROFILES.items()
        },
        "optional_plans": {key: plan.contract() for key, plan in POWER_PLANS.items()},
        "connection_limits": (
            "Selected optional tether topology: 24 V PSU -> one BEC12S-PRO set to 8 V -> FC/main input and SVPDB-8S input in parallel; the SVPDB default 5 V output supplies servo positives. This cascade is an integration inference from manufacturer voltage ranges, not a qualified complete system.",
            "Set the BEC12S-PRO from its shipping default 5.2 V to 8 V and measure the unloaded output before connecting loads. Leave SVPDB-8S at its default 5 V. Exact 5.2 V servo power is not required by this plan.",
            "The BEC's published 5 A output at 8 V is shared by main loads and SVPDB input. I_BEC8 = I_main8 + (5*I_servo5)/(8*eta_SVPDB), with eta including conversion losses and not assigned a verified value. At the SVPDB's published 4 A output, its input needs more than the ideal 2.5 A at 8 V. Peak ratings are not continuous or guaranteed simultaneous margin.",
            "Keep servo-positive wires off the FC 5 V rail when using SVPDB. Share ground and preserve individual control signals. F-Mini and other peripherals stay on the FC's appropriate supply. Never join the two regulated 5 V output positives, even though their nominal voltages match.",
            "Battery and tether are mutually exclusive supply choices here; no automatic changeover, charging or parallel battery/PSU operation is designed.",
            "The selected FC's published input-range conflict is unresolved for both existing 2S operation and an 8 V tether output. Preserve the selected board, but do not claim those supply combinations qualified.",
            "There is no dedicated tether guide or rated anchor. Secure the incoming lead to suitable existing structure before the PCB terminals. Whole-tether load capacity, cable rating, loss, strain relief and freedom from propeller/optical interference during flight remain installation checks.",
        ),
    }
