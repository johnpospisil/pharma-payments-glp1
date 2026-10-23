from ppg.ingest.reference import DAC_DROP

DAC_HEADER = [
    "NPI",
    "Ind_PAC_ID",
    "Ind_enrl_ID",
    "Provider Last Name",
    "Provider First Name",
    "Provider Middle Name",
    "suff",
    "gndr",
    "Cred",
    "Med_sch",
    "Grd_yr",
    "pri_spec",
    "sec_spec_all",
    "Telehlth",
    "Facility Name",
    "org_pac_id",
    "num_org_mem",
    "adr_ln_1",
    "adr_ln_2",
    "ln_2_sprs",
    "City/Town",
    "State",
    "ZIP Code",
    "Telephone Number",
    "ind_assgn",
    "grp_assgn",
    "adrs_id",
]


def test_dac_drops_names_addresses_phone():
    dropped = {c for c in DAC_HEADER if DAC_DROP.search(c)}
    assert dropped == {
        "Provider Last Name",
        "Provider First Name",
        "Provider Middle Name",
        "suff",
        "Facility Name",
        "adr_ln_1",
        "adr_ln_2",
        "ln_2_sprs",
        "City/Town",
        "Telephone Number",
        "adrs_id",
    }


def test_dac_keeps_linkage_fields():
    kept = {c for c in DAC_HEADER if not DAC_DROP.search(c)}
    assert {"NPI", "org_pac_id", "num_org_mem", "pri_spec", "Grd_yr", "State", "ZIP Code"} <= kept
