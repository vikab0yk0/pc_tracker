import logging
from concurrent import futures
import grpc

from src.protos import compatibility_pb2 as pb2
from src.protos import compatibility_pb2_grpc as pb2_grpc

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gRPC-Server")


class CompatibilityServicer(pb2_grpc.CompatibilityServiceServicer):
    """Реализация удаленного сервиса проверки совместимости комплектующих ПК."""

    def CheckCompatibility(self, request: pb2.CompatibilityRequest, context) -> pb2.CompatibilityResponse:
        logger.info(f"Получен запрос валидации для сборки ID={request.build_id}, компонентов: {len(request.components)}")

        errors = []
        warnings = []
        total_tdp = 70

        cpu = None
        motherboard = None
        ram_list = []
        gpu_list = []
        psu = None
        case = None


        for comp in request.components:
            slug = comp.category_slug.lower()
            if slug == "cpu":
                cpu = comp
                total_tdp += comp.tdp
            elif slug in ("motherboard", "mb"):
                motherboard = comp
            elif slug == "ram":
                ram_list.append(comp)
            elif slug == "gpu":
                gpu_list.append(comp)
                total_tdp += (comp.tdp * comp.quantity)
            elif slug == "psu":
                psu = comp
            elif slug == "case":
                case = comp


        if cpu and motherboard:
            if cpu.socket and motherboard.socket and cpu.socket.strip().lower() != motherboard.socket.strip().lower():
                errors.append(
                    f"Несовместимость сокетов: Процессор ({cpu.model_name}) использует сокет {cpu.socket}, "
                    f"а материнская плата ({motherboard.model_name}) — {motherboard.socket}."
                )


        if motherboard and ram_list:
            for ram in ram_list:
                if motherboard.ram_type and ram.ram_type and motherboard.ram_type.strip().lower() != ram.ram_type.strip().lower():
                    errors.append(
                        f"Несовместимость типа ОЗУ: Плата требует {motherboard.ram_type}, "
                        f"а модуль {ram.model_name} имеет тип {ram.ram_type}."
                    )


        if motherboard and ram_list and motherboard.ram_slots > 0:
            total_sticks = sum(ram.quantity * max(1, ram.kit_count) for ram in ram_list)
            if total_sticks > motherboard.ram_slots:
                errors.append(
                    f"Превышено количество слотов ОЗУ: Устанавливается {total_sticks} модулей, "
                    f"но материнская плата поддерживает максимум {motherboard.ram_slots}."
                )


        if case and gpu_list and case.max_gpu_len_mm > 0:
            for gpu in gpu_list:
                if gpu.length_mm > case.max_gpu_len_mm:
                    errors.append(
                        f"Видеокарта {gpu.model_name} длиной {gpu.length_mm} мм не помещается "
                        f"в корпус с ограничением {case.max_gpu_len_mm} мм."
                    )


        recommended_psu = int(total_tdp * 1.3) + 50
        if psu and psu.psu_wattage > 0:
            if psu.psu_wattage < total_tdp:
                errors.append(
                    f"Критическая нехватка мощности: Мощность БП ({psu.psu_wattage} Вт) меньше "
                    f"энергопотребления системы ({total_tdp} Вт)."
                )
            elif psu.psu_wattage < recommended_psu:
                warnings.append(
                    f"Мощность БП ({psu.psu_wattage} Вт) близка к пределу. "
                    f"Рекомендуется БП от {recommended_psu} Вт для стабильной работы."
                )

        is_compatible = len(errors) == 0

        return pb2.CompatibilityResponse(
            is_compatible=is_compatible,
            errors=errors,
            warnings=warnings,
            total_estimated_wattage=total_tdp,
            recommended_psu_wattage=recommended_psu
        )


def serve(host: str = "0.0.0.0", port: int = 50051):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_CompatibilityServiceServicer_to_server(CompatibilityServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    logger.info(f"gRPC Сервер запущен на {host}:{port}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()