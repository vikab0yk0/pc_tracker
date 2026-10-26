import pytest
import requests
from src.protos import compatibility_pb2 as pb2
from src.grpc_services.server import CompatibilityServicer


class TestGrpcCompatibilityService:
    """Модульные тесты бизнес-логики Servicer без необходимости сетевого стека."""

    def test_compatible_am5_setup(self):
        servicer = CompatibilityServicer()
        request = pb2.CompatibilityRequest(
            build_id=1,
            components=[
                pb2.ComponentData(category_slug="cpu", model_name="Ryzen 5 7600", socket="AM5", tdp=65),
                pb2.ComponentData(category_slug="motherboard", model_name="B650 Board", socket="AM5", ram_type="DDR5", ram_slots=4),
                pb2.ComponentData(category_slug="ram", model_name="16GB DDR5", ram_type="DDR5", quantity=2, kit_count=1),
                pb2.ComponentData(category_slug="psu", model_name="650W PSU", psu_wattage=650)
            ]
        )
        response = servicer.CheckCompatibility(request, None)

        assert response.is_compatible is True
        assert len(response.errors) == 0
        assert response.total_estimated_wattage > 0

    def test_incompatible_sockets_detected(self):
        servicer = CompatibilityServicer()
        request = pb2.CompatibilityRequest(
            build_id=2,
            components=[
                pb2.ComponentData(category_slug="cpu", model_name="Intel Core i5-13600K", socket="LGA1700", tdp=125),
                pb2.ComponentData(category_slug="motherboard", model_name="AMD B650 Board", socket="AM5")
            ]
        )
        response = servicer.CheckCompatibility(request, None)

        assert response.is_compatible is False
        assert any("сокетов" in err.lower() for err in response.errors)

    def test_gpu_case_dimension_conflict(self):
        servicer = CompatibilityServicer()
        request = pb2.CompatibilityRequest(
            build_id=3,
            components=[
                pb2.ComponentData(category_slug="gpu", model_name="RTX 4090", length_mm=350, quantity=1, tdp=450),
                pb2.ComponentData(category_slug="case", model_name="Compact ITX Case", max_gpu_len_mm=300)
            ]
        )
        response = servicer.CheckCompatibility(request, None)

        assert response.is_compatible is False
        assert any("не помещается" in err.lower() for err in response.errors)


class TestRestToGrpcIntegration:
    """Интеграционный тест: REST API -> gRPC Microservice."""

    def test_api_compatibility_endpoint(
        self, session: requests.Session, api_url: str, user_auth: dict, admin_auth: dict, test_category: int
    ):
        build_resp = session.post(
            f"{api_url}/builds/",
            json={"name": "gRPC Test Rig", "description": "Validation test"},
            headers=user_auth["headers"]
        )
        assert build_resp.status_code == 201
        build_id = build_resp.json()["id"]

        comp_resp = session.get(
            f"{api_url}/builds/{build_id}/compatibility",
            headers=user_auth["headers"]
        )

        assert comp_resp.status_code == 200
        data = comp_resp.json()
        assert "is_compatible" in data
        assert "total_estimated_wattage" in data
        assert "recommended_psu_wattage" in data
        assert data["build_id"] == build_id
