import grpc
from src.protos import compatibility_pb2 as pb2
from src.protos import compatibility_pb2_grpc as pb2_grpc


class CompatibilityGrpcClient:
    """Клиент для выполнения удаленных вызовов к микросервису совместимости."""

    def __init__(self, target: str = "127.0.0.1:50051"):
        self.channel = grpc.insecure_channel(target)
        self.stub = pb2_grpc.CompatibilityServiceStub(self.channel)

    def check_build(self, build_id: int, components_data: list[dict]) -> dict:
        proto_components = []
        for item in components_data:
            specs = item.get("specs", {})
            proto_components.append(
                pb2.ComponentData(
                    category_slug=item.get("category_slug", ""),
                    model_name=item.get("model_name", ""),
                    quantity=item.get("quantity", 1),
                    socket=str(specs.get("socket", "")),
                    tdp=int(specs.get("tdp", 0)),
                    ram_type=str(specs.get("ram_type", "")),
                    ram_slots=int(specs.get("ram_slots", 0)),
                    kit_count=int(specs.get("kit_count", 1)),
                    length_mm=int(specs.get("length_mm", 0)),
                    max_gpu_len_mm=int(specs.get("max_gpu_len", specs.get("max_gpu_len_mm", 0))),
                    cooler_height_mm=int(specs.get("cooler_height_mm", 0)),
                    max_cooler_height_mm=int(specs.get("max_cooler_height_mm", 0)),
                    psu_wattage=int(specs.get("psu_wattage", specs.get("wattage", 0))),
                )
            )

        request = pb2.CompatibilityRequest(
            build_id=build_id,
            components=proto_components
        )

        response = self.stub.CheckCompatibility(request, timeout=3.0)

        return {
            "is_compatible": response.is_compatible,
            "errors": list(response.errors),
            "warnings": list(response.warnings),
            "total_estimated_wattage": response.total_estimated_wattage,
            "recommended_psu_wattage": response.recommended_psu_wattage
        }