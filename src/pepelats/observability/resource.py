"""The OTel Resource shared by all three signals, built from service identity."""

from opentelemetry.sdk.resources import Resource

from pepelats.configuration import ServiceConfig


def build_resource(service: ServiceConfig) -> Resource:
    return Resource.create(
        {
            "service.name": service.service_name,
            "service.version": service.service_version,
            "service.instance.id": service.instance_id,
        }
    )
