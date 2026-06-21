"""OHDSI WebAPI proxy endpoints to avoid CORS issues with external OHDSI instances."""

import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ohdsi", tags=["OHDSI Proxy"])


class OHDSIProxyRequest(BaseModel):
    webapi_url: str


class CohortCriteriaRequest(BaseModel):
    primary_condition_concept_id: int
    primary_condition_name: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    gender_concept_id: Optional[int] = None
    observation_period_days: int = 365


class CreateCohortRequest(BaseModel):
    webapi_url: str
    cohort_name: str
    description: Optional[str] = None
    criteria: CohortCriteriaRequest


def normalize_webapi_url(url: str) -> str:
    """Normalize the WebAPI URL (port 8081 to 8080, add /WebAPI if missing)."""
    base_url = url.rstrip('/')

    if ":8081" in base_url:
        base_url = base_url.replace(":8081", ":8080")

    if "/WebAPI" not in base_url and "/webapi" not in base_url.lower():
        base_url = f"{base_url}/WebAPI"

    return base_url


@router.get("/sources")
async def get_cdm_sources(webapi_url: str = Query(..., description="OHDSI WebAPI base URL")):
    """Fetch available CDM sources from an OHDSI WebAPI instance."""
    try:
        base_url = normalize_webapi_url(webapi_url)
        source_url = f"{base_url}/source/sources"

        logger.info(f"Fetching CDM sources from: {source_url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(source_url, headers={"Accept": "application/json"})

            if response.status_code == 200:
                sources = response.json()
                if isinstance(sources, list):
                    logger.info(f"Successfully fetched {len(sources)} CDM sources")
                    return sources

            raise HTTPException(
                status_code=502,
                detail=f"Could not connect to OHDSI WebAPI at {source_url}. Response: {response.status_code}"
            )

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection to WebAPI timed out")
    except httpx.RequestError as e:
        logger.error(f"Error connecting to OHDSI WebAPI: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to WebAPI: {str(e)}")


@router.get("/cohort/{cohort_id}")
async def get_cohort_definition(
    cohort_id: int,
    webapi_url: str = Query(..., description="OHDSI WebAPI base URL")
):
    """Fetch cohort definition from an OHDSI WebAPI instance."""
    try:
        base_url = normalize_webapi_url(webapi_url)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/cohortdefinition/{cohort_id}",
                headers={"Accept": "application/json"}
            )

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Cohort {cohort_id} not found")

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch cohort: {response.text}"
                )

            cohort_def = response.json()
            logger.info(f"Fetched cohort {cohort_id}: {cohort_def.get('name', 'Unknown')}")
            return cohort_def

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection to WebAPI timed out")
    except httpx.RequestError as e:
        logger.error(f"Error connecting to OHDSI WebAPI: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to WebAPI: {str(e)}")


@router.get("/cohort/{cohort_id}/info")
async def get_cohort_generation_info(
    cohort_id: int,
    webapi_url: str = Query(..., description="OHDSI WebAPI base URL"),
    source_key: Optional[str] = Query(None, description="Optional source key to filter")
):
    """Fetch cohort generation info (person count, status) from an OHDSI WebAPI instance."""
    try:
        base_url = normalize_webapi_url(webapi_url)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{base_url}/cohortdefinition/{cohort_id}/info",
                headers={"Accept": "application/json"}
            )

            if response.status_code != 200:
                return []

            gen_info = response.json()

            if source_key and isinstance(gen_info, list):
                gen_info = [
                    g for g in gen_info
                    if g.get('id', {}).get('sourceId') == source_key or
                       g.get('sourceKey') == source_key
                ]

            return gen_info

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection to WebAPI timed out")
    except httpx.RequestError as e:
        logger.error(f"Error connecting to OHDSI WebAPI: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to WebAPI: {str(e)}")


@router.get("/cohort/{cohort_id}/full")
async def get_cohort_full_details(
    cohort_id: int,
    webapi_url: str = Query(..., description="OHDSI WebAPI base URL"),
    source_key: Optional[str] = Query(None, description="Source key to get generation status")
):
    """Fetch complete cohort details: definition and generation status."""
    try:
        base_url = normalize_webapi_url(webapi_url)

        async with httpx.AsyncClient(timeout=30.0) as client:
            def_response = await client.get(
                f"{base_url}/cohortdefinition/{cohort_id}",
                headers={"Accept": "application/json"}
            )

            if def_response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Cohort {cohort_id} not found")

            if def_response.status_code != 200:
                raise HTTPException(
                    status_code=def_response.status_code,
                    detail=f"Failed to fetch cohort: {def_response.text}"
                )

            cohort_def = def_response.json()

            generation_info = None
            try:
                gen_response = await client.get(
                    f"{base_url}/cohortdefinition/{cohort_id}/info",
                    headers={"Accept": "application/json"}
                )

                if gen_response.status_code == 200:
                    gen_info_list = gen_response.json()

                    if source_key and isinstance(gen_info_list, list):
                        for g in gen_info_list:
                            if (str(g.get('id', {}).get('sourceId')) == str(source_key) or
                                g.get('sourceKey') == source_key):
                                generation_info = g
                                break
                    elif gen_info_list:
                        generation_info = gen_info_list[0] if isinstance(gen_info_list, list) else gen_info_list

            except Exception as e:
                logger.warning(f"Could not fetch generation info: {e}")

            result = {
                "id": cohort_def.get("id"),
                "name": cohort_def.get("name"),
                "description": cohort_def.get("description"),
                "createdDate": cohort_def.get("createdDate"),
                "modifiedDate": cohort_def.get("modifiedDate"),
                "expressionType": cohort_def.get("expressionType"),
                "personCount": None,
                "status": "UNKNOWN",
                "generationInfo": generation_info
            }

            if generation_info:
                result["personCount"] = generation_info.get("personCount")
                result["status"] = generation_info.get("status", "UNKNOWN")

            logger.info(f"Fetched full details for cohort {cohort_id}: {result['name']} ({result['personCount']} persons)")
            return result

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection to WebAPI timed out")
    except httpx.RequestError as e:
        logger.error(f"Error connecting to OHDSI WebAPI: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to WebAPI: {str(e)}")


def build_cohort_expression(criteria: CohortCriteriaRequest) -> Dict[str, Any]:
    """Build an OHDSI CIRCE cohort expression JSON from the provided criteria."""
    concept_set = {
        "id": 0,
        "name": criteria.primary_condition_name or f"Condition {criteria.primary_condition_concept_id}",
        "expression": {
            "items": [
                {
                    "concept": {
                        "CONCEPT_ID": criteria.primary_condition_concept_id,
                        "CONCEPT_NAME": criteria.primary_condition_name or "Primary Condition",
                        "STANDARD_CONCEPT": "S",
                        "STANDARD_CONCEPT_CAPTION": "Standard",
                        "INVALID_REASON": "V",
                        "INVALID_REASON_CAPTION": "Valid",
                        "CONCEPT_CODE": str(criteria.primary_condition_concept_id),
                        "DOMAIN_ID": "Condition",
                        "VOCABULARY_ID": "SNOMED"
                    },
                    "isExcluded": False,
                    "includeDescendants": True,
                    "includeMapped": True
                }
            ]
        }
    }

    primary_criteria = {
        "CriteriaList": [
            {
                "ConditionOccurrence": {
                    "CodesetId": 0,
                    "First": True
                }
            }
        ],
        "ObservationWindow": {
            "PriorDays": criteria.observation_period_days,
            "PostDays": 0
        },
        "PrimaryCriteriaLimit": {
            "Type": "First"
        }
    }

    inclusion_rules = []

    if criteria.age_min is not None or criteria.age_max is not None:
        age_criteria = {"Age": {}}
        if criteria.age_min is not None:
            age_criteria["Age"]["Value"] = criteria.age_min
            age_criteria["Age"]["Op"] = "gte"
        if criteria.age_max is not None:
            if criteria.age_min is not None:
                age_criteria["Age"]["Extent"] = criteria.age_max
                age_criteria["Age"]["Op"] = "bt"
            else:
                age_criteria["Age"]["Value"] = criteria.age_max
                age_criteria["Age"]["Op"] = "lte"

        inclusion_rules.append({
            "name": f"Age {criteria.age_min or ''}-{criteria.age_max or ''}",
            "expression": {
                "Type": "ALL",
                "CriteriaList": [],
                "DemographicCriteriaList": [age_criteria],
                "Groups": []
            }
        })

    if criteria.gender_concept_id:
        gender_name = "Male" if criteria.gender_concept_id == 8507 else "Female" if criteria.gender_concept_id == 8532 else "Other"
        inclusion_rules.append({
            "name": f"Gender: {gender_name}",
            "expression": {
                "Type": "ALL",
                "CriteriaList": [],
                "DemographicCriteriaList": [
                    {
                        "Gender": [
                            {"CONCEPT_ID": criteria.gender_concept_id}
                        ]
                    }
                ],
                "Groups": []
            }
        })

    expression = {
        "ConceptSets": [concept_set],
        "PrimaryCriteria": primary_criteria,
        "QualifiedLimit": {"Type": "First"},
        "ExpressionLimit": {"Type": "First"},
        "InclusionRules": inclusion_rules,
        "CensoringCriteria": [],
        "CollapseSettings": {
            "CollapseType": "ERA",
            "EraPad": 0
        },
        "CensorWindow": {}
    }

    return expression


@router.post("/cohort/create")
async def create_cohort(request: CreateCohortRequest):
    """Create a new cohort definition in OHDSI WebAPI (generation triggered separately in ATLAS)."""
    try:
        base_url = normalize_webapi_url(request.webapi_url)

        expression = build_cohort_expression(request.criteria)

        cohort_payload = {
            "name": request.cohort_name,
            "description": request.description or f"Cohort created via SMART for condition {request.criteria.primary_condition_concept_id}",
            "expressionType": "SIMPLE_EXPRESSION",
            "expression": expression,
        }

        logger.info(f"Creating cohort '{request.cohort_name}' at {base_url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/cohortdefinition",
                json=cohort_payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )

            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Successfully created cohort: {result.get('id')} - {result.get('name')}")
                return {
                    "id": result.get("id"),
                    "name": result.get("name"),
                    "description": result.get("description"),
                    "createdDate": result.get("createdDate"),
                    "status": "CREATED",
                    "message": "Cohort definition created. Generate the cohort in ATLAS to get person counts."
                }
            else:
                error_text = response.text
                logger.error(f"Failed to create cohort: {response.status_code} - {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to create cohort: {error_text}"
                )

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection to WebAPI timed out")
    except httpx.RequestError as e:
        logger.error(f"Error connecting to OHDSI WebAPI: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to WebAPI: {str(e)}")


@router.get("/cohort/{cohort_id}/heracles")
async def get_heracles_characterization(
    cohort_id: int,
    webapi_url: str = Query(..., description="OHDSI WebAPI base URL"),
    source_key: str = Query(..., description="CDM source key")
):
    """Fetch Heracles characterization reports for a cohort and return Section 3 auto-fill data."""
    try:
        base_url = normalize_webapi_url(webapi_url)

        async with httpx.AsyncClient(timeout=60.0) as client:
            cohort_response = await client.get(
                f"{base_url}/cohortdefinition/{cohort_id}",
                headers={"Accept": "application/json"}
            )

            cohort_def = None
            concept_sets = []
            cohort_criteria = {"inclusion_rules": [], "exclusion_rules": [], "observation_window": None}

            if cohort_response.status_code == 200:
                cohort_def = cohort_response.json()

                expression_str = cohort_def.get("expression", "{}")
                try:
                    if isinstance(expression_str, str):
                        expression = json.loads(expression_str)
                    else:
                        expression = expression_str

                    for cs in expression.get("ConceptSets", []):
                        concept_ids = []
                        concept_names = []
                        for item in cs.get("expression", {}).get("items", []):
                            concept = item.get("concept", {})
                            if concept.get("CONCEPT_ID"):
                                concept_ids.append(concept["CONCEPT_ID"])
                            if concept.get("CONCEPT_NAME"):
                                concept_names.append(concept["CONCEPT_NAME"])

                        concept_sets.append({
                            "id": cs.get("id"),
                            "name": cs.get("name", f"Concept Set {cs.get('id')}"),
                            "concept_ids": concept_ids,
                            "concept_names": concept_names,
                            "description": f"{len(concept_ids)} concept(s): {', '.join(concept_names[:3])}" + ("..." if len(concept_names) > 3 else "")
                        })

                    if "PrimaryCriteria" in expression:
                        pc = expression["PrimaryCriteria"]
                        criteria_list = pc.get("CriteriaList", [])
                        for criterion in criteria_list:
                            if isinstance(criterion, dict):
                                for key, val in criterion.items():
                                    if key != "CorrelatedCriteria":
                                        criterion_type = key.replace('Occurrence', ' Occurrence')
                                        rule = f"Patients with {criterion_type}"
                                        if isinstance(val, dict) and "CodesetId" in val:
                                            codeset_id = val["CodesetId"]
                                            for cs in concept_sets:
                                                if cs.get("id") == codeset_id:
                                                    rule += f" (concept set: {cs['name']})"
                                                    break
                                        cohort_criteria["inclusion_rules"].append(rule)

                        if "ObservationWindow" in pc:
                            obs = pc["ObservationWindow"]
                            prior = obs.get("PriorDays", 0)
                            post = obs.get("PostDays", 0)
                            cohort_criteria["observation_window"] = f"{prior} days prior, {post} days after index"

                    for rule in expression.get("InclusionRules", []):
                        name = rule.get('name', '')
                        desc = rule.get('description', '')
                        if name and not ('demo' in name.lower() and not desc):
                            cohort_criteria["inclusion_rules"].append(f"{name}: {desc}" if desc else name)

                    for censor in expression.get("CensoringCriteria", []):
                        if isinstance(censor, dict):
                            for key in censor.keys():
                                cohort_criteria["exclusion_rules"].append(f"Exclude patients with {key.replace('Occurrence', ' Occurrence')}")

                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Could not parse cohort expression: {e}")

            demographics = {}
            detailed_reports = {
                "person": None,
                "dashboard": None,
                "condition": None
            }
            heracles_available = False

            try:
                person_response = await client.get(
                    f"{base_url}/cohortresults/{source_key}/{cohort_id}/person",
                    headers={"Accept": "application/json"}
                )

                if person_response.status_code == 200:
                    person_data = person_response.json()
                    heracles_available = True

                    detailed_reports["person"] = person_data

                    gender_data = person_data.get("gender", [])
                    if gender_data:
                        total_gender = sum(g.get("countValue", 0) for g in gender_data)
                        gender_parts = []
                        gender_detailed = []
                        for g in gender_data:
                            name = g.get("conceptName", "Unknown")
                            concept_id = g.get("conceptId", 0)
                            count = g.get("countValue", 0)
                            pct = (count / total_gender * 100) if total_gender > 0 else 0
                            gender_parts.append(f"{name}: {count} ({pct:.1f}%)")
                            gender_detailed.append({
                                "name": name,
                                "concept_id": concept_id,
                                "count": count,
                                "percentage": round(pct, 2)
                            })
                        demographics["gender_distribution"] = ", ".join(gender_parts)
                        demographics["gender_detailed"] = gender_detailed

                    yob_stats = person_data.get("yearOfBirthStats", [])
                    yob_dist = person_data.get("yearOfBirth", [])

                    if yob_stats and isinstance(yob_stats, list) and len(yob_stats) > 0:
                        stat = yob_stats[0]
                        current_year = datetime.now().year
                        min_yob = stat.get("minValue", current_year - 80)
                        max_yob = stat.get("maxValue", current_year - 20)
                        interval_size = stat.get("intervalSize", 1)

                        age_min = current_year - max_yob
                        age_max = current_year - min_yob

                        if yob_dist:
                            total_count = sum(item.get("countValue", 0) for item in yob_dist)
                            weighted_sum = 0
                            age_detailed = []

                            for item in yob_dist:
                                yob = min_yob + item.get("intervalIndex", 0) * interval_size
                                age = current_year - yob
                                count = item.get("countValue", 0)
                                pct = item.get("percentValue", 0) * 100
                                weighted_sum += age * count
                                age_detailed.append({
                                    "year_of_birth": yob,
                                    "age": age,
                                    "count": count,
                                    "percentage": round(pct, 2)
                                })

                            mean_age = weighted_sum / total_count if total_count > 0 else 0
                            demographics["age_distribution"] = f"Mean: {mean_age:.1f} years, Range: {age_min}-{age_max} (birth years {min_yob}-{max_yob})"
                            demographics["age_detailed"] = sorted(age_detailed, key=lambda x: x["age"], reverse=True)
                        else:
                            demographics["age_distribution"] = f"Range: {age_min}-{age_max} years (birth years {min_yob}-{max_yob})"

                    race_data = person_data.get("race", [])
                    if race_data:
                        race_parts = []
                        race_detailed = []
                        total_race = sum(r.get("countValue", 0) for r in race_data if r.get("conceptName", "").lower() != "no matching concept")

                        for r in race_data:
                            name = r.get("conceptName", "Unknown")
                            concept_id = r.get("conceptId", 0)
                            count = r.get("countValue", 0)

                            if "no matching" in name.lower():
                                race_detailed.append({
                                    "name": "Not recorded",
                                    "concept_id": concept_id,
                                    "count": count,
                                    "percentage": None
                                })
                                continue

                            pct = (count / total_race * 100) if total_race > 0 else 0
                            race_parts.append(f"{name}: {count} ({pct:.1f}%)")
                            race_detailed.append({
                                "name": name,
                                "concept_id": concept_id,
                                "count": count,
                                "percentage": round(pct, 2)
                            })

                        if race_parts:
                            demographics["race_distribution"] = ", ".join(race_parts)
                        else:
                            demographics["race_distribution"] = "Not recorded in source data"
                        demographics["race_detailed"] = race_detailed

                    ethnicity_data = person_data.get("ethnicity", [])
                    if ethnicity_data:
                        eth_parts = []
                        eth_detailed = []
                        total_eth = sum(e.get("countValue", 0) for e in ethnicity_data if e.get("conceptName", "").lower() != "no matching concept")

                        for e in ethnicity_data:
                            name = e.get("conceptName", "Unknown")
                            concept_id = e.get("conceptId", 0)
                            count = e.get("countValue", 0)

                            if "no matching" in name.lower():
                                eth_detailed.append({
                                    "name": "Not recorded",
                                    "concept_id": concept_id,
                                    "count": count,
                                    "percentage": None
                                })
                                continue

                            pct = (count / total_eth * 100) if total_eth > 0 else 0
                            eth_parts.append(f"{name}: {count} ({pct:.1f}%)")
                            eth_detailed.append({
                                "name": name,
                                "concept_id": concept_id,
                                "count": count,
                                "percentage": round(pct, 2)
                            })

                        if eth_parts:
                            demographics["ethnicity_distribution"] = ", ".join(eth_parts)
                        else:
                            demographics["ethnicity_distribution"] = "Not recorded in source data"
                        demographics["ethnicity_detailed"] = eth_detailed

            except Exception as e:
                logger.warning(f"Could not fetch person characterization: {e}")

            try:
                dashboard_response = await client.get(
                    f"{base_url}/cohortresults/{source_key}/{cohort_id}/dashboard",
                    headers={"Accept": "application/json"}
                )
                if dashboard_response.status_code == 200:
                    dashboard_data = dashboard_response.json()
                    detailed_reports["dashboard"] = dashboard_data
                    heracles_available = True
            except Exception as e:
                logger.warning(f"Could not fetch dashboard: {e}")

            condition_summary = []
            try:
                condition_response = await client.get(
                    f"{base_url}/cohortresults/{source_key}/{cohort_id}/condition",
                    headers={"Accept": "application/json"}
                )
                if condition_response.status_code == 200:
                    condition_data = condition_response.json()
                    detailed_reports["condition"] = condition_data
                    heracles_available = True

                    if isinstance(condition_data, list):
                        sorted_conditions = sorted(condition_data, key=lambda x: x.get("numPersons", 0), reverse=True)
                        for cond in sorted_conditions[:10]:
                            concept_id = cond.get("conceptId")
                            concept_path = cond.get("conceptPath", "")
                            name = concept_path.split("||")[-1] if concept_path else f"Concept {concept_id}"
                            num_persons = cond.get("numPersons", 0)
                            pct_persons = cond.get("percentPersons", 0) * 100
                            records_per_person = cond.get("recordsPerPerson", 0)

                            condition_summary.append({
                                "concept_id": concept_id,
                                "name": name,
                                "num_persons": num_persons,
                                "percent_persons": round(pct_persons, 1),
                                "records_per_person": round(records_per_person, 2)
                            })
            except Exception as e:
                logger.warning(f"Could not fetch condition report: {e}")

            source_id = None
            try:
                sources_response = await client.get(
                    f"{base_url}/source/sources",
                    headers={"Accept": "application/json"}
                )
                if sources_response.status_code == 200:
                    sources = sources_response.json()
                    for src in sources:
                        if src.get("sourceKey") == source_key:
                            source_id = src.get("sourceId")
                            break
            except Exception as e:
                logger.warning(f"Could not fetch sources to resolve source_key: {e}")

            person_count = None
            cohort_status = "UNKNOWN"
            try:
                gen_response = await client.get(
                    f"{base_url}/cohortdefinition/{cohort_id}/info",
                    headers={"Accept": "application/json"}
                )

                if gen_response.status_code == 200:
                    gen_info_list = gen_response.json()
                    for g in gen_info_list:
                        gen_source_id = g.get('id', {}).get('sourceId') if isinstance(g.get('id'), dict) else None
                        if (source_id and gen_source_id == source_id) or \
                           (str(gen_source_id) == str(source_key)) or \
                           g.get('sourceKey') == source_key:
                            person_count = g.get("personCount")
                            cohort_status = g.get("status", "UNKNOWN")
                            break
                    if person_count is None and len(gen_info_list) == 1:
                        person_count = gen_info_list[0].get("personCount")
                        cohort_status = gen_info_list[0].get("status", "UNKNOWN")
            except Exception as e:
                logger.warning(f"Could not fetch generation info: {e}")

            pop_chars_parts = []
            if cohort_def:
                pop_chars_parts.append(f"Cohort: {cohort_def.get('name', 'Unknown')}")
            if person_count:
                pop_chars_parts.append(f"Total subjects: {person_count:,}")
            if demographics.get("age_distribution"):
                pop_chars_parts.append(f"Age: {demographics['age_distribution']}")
            if demographics.get("gender_distribution"):
                pop_chars_parts.append(f"Gender: {demographics['gender_distribution']}")
            if concept_sets:
                cs_names = [cs["name"] for cs in concept_sets[:3]]
                pop_chars_parts.append(f"Clinical phenotypes: {', '.join(cs_names)}" + ("..." if len(concept_sets) > 3 else ""))

            dist_parts = []
            if person_count:
                dist_parts.append(f"Total Cohort Size: {person_count:,} patients extracted from OMOP CDM")
            if demographics.get("age_distribution"):
                dist_parts.append(f"Age Distribution: {demographics['age_distribution']}")
            if demographics.get("gender_distribution"):
                dist_parts.append(f"Gender Distribution: {demographics['gender_distribution']}")
            if demographics.get("race_distribution"):
                dist_parts.append(f"Race: {demographics['race_distribution']}")
            if demographics.get("ethnicity_distribution"):
                dist_parts.append(f"Ethnicity: {demographics['ethnicity_distribution']}")
            if condition_summary:
                top_conds = [c["name"] for c in condition_summary[:3]]
                dist_parts.append(f"Top Conditions: {', '.join(top_conds)}")

            if heracles_available:
                dist_parts.append("Data characterized using OHDSI Heracles with standardized vocabularies (SNOMED CT, ICD-10, LOINC, RxNorm)")

            collection_period = None
            if cohort_def:
                created = cohort_def.get("createdDate")
                modified = cohort_def.get("modifiedDate")
                if created:
                    try:
                        if isinstance(created, (int, float)):
                            created_date = datetime.fromtimestamp(created / 1000).strftime("%Y-%m-%d")
                        else:
                            created_date = str(created)[:10]
                        collection_period = f"Cohort defined: {created_date}"
                        if modified and modified != created:
                            if isinstance(modified, (int, float)):
                                modified_date = datetime.fromtimestamp(modified / 1000).strftime("%Y-%m-%d")
                            else:
                                modified_date = str(modified)[:10]
                            collection_period = f"Cohort defined: {created_date}, Modified: {modified_date}"
                    except Exception:
                        pass

            result = {
                "cohort_id": cohort_id,
                "source_key": source_key,
                "cohort_name": cohort_def.get("name") if cohort_def else None,
                "cohort_description": cohort_def.get("description") if cohort_def else None,
                "heracles_available": heracles_available,
                "person_count": person_count,
                "cohort_status": cohort_status,

                "demographics": demographics,
                "population_characteristics": ". ".join(pop_chars_parts) if pop_chars_parts else None,
                "data_distribution_summary": ". ".join(dist_parts) if dist_parts else None,
                "collection_period": collection_period,

                "concept_sets": concept_sets,
                "cohort_criteria": cohort_criteria,
                "condition_summary": condition_summary,

                "detailed_reports": detailed_reports,

                "data_governance_template": (
                    f"Data Source: OMOP CDM via OHDSI WebAPI ({source_key}). "
                    f"Cohort ID: {cohort_id}. "
                    "Data access: Authenticated OHDSI WebAPI endpoint. "
                    "Standardized vocabularies: SNOMED CT, ICD-10, LOINC, RxNorm. "
                    "De-identification: As per source CDM configuration."
                ),

                "data_representativeness_template": (
                    f"Data from OMOP CDM source '{source_key}'. "
                    f"Cohort of {person_count:,} subjects meeting phenotype criteria. " if person_count else ""
                    "Representativeness depends on source healthcare system coverage, "
                    "patient population demographics, and data capture completeness."
                )
            }

            logger.info(f"Fetched Heracles data for cohort {cohort_id}: heracles_available={heracles_available}, person_count={person_count}")
            return result

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Connection to WebAPI timed out")
    except httpx.RequestError as e:
        logger.error(f"Error connecting to OHDSI WebAPI: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to WebAPI: {str(e)}")
