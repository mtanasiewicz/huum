from urllib.parse import urljoin
from enum import IntEnum
from typing import Dict
from typing import Optional
from pydantic import BaseModel
from .settings import settings
from .schemas import HuumStatusResponse

import aiohttp, logging
_LOGGER = logging.getLogger(__name__)

API_BASE = "https://api.huum.eu/action/home/"


class Huum:
    """
    Usage:
        # Usage with env vars
        huum = Huum()

        # Setting auth variables explicitly
        huum = Huum(username="foo", password="bar")

        # If you don't have an existing aiohttp session
        # then run `open_session()` after initilizing
        huum.open_session()

        # Turn on the sauna
        huum.turn_on(80)
    """

    min_temp = 40
    max_temp = 110

    session: aiohttp.ClientSession

    def __init__(
        self,
        username: Optional[str] = settings.huum_username,
        password: Optional[str] = settings.huum_password,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        if session:
            self.session = session

        if not username or not password:
            raise ValueError(
                "No username or password provided either by the environment nor explicitly"
            )
        self.auth = aiohttp.BasicAuth(username, password)

    async def _check_door(self) -> None:
        """
        Check if the door is closed, if not, raise an exception
        """
        status = await self.status()
        if not status.door_closed:
            raise SafetyException("Can not start sauna when door is open")

    async def turn_on(
        self, temperature: int, safety_override: bool = False
    ) -> HuumStatusResponse:
        """
        Turns on the sauna at a given temperature

        Args:
            temperature: Target temperature to set the sauna to
            safety_override: If False, check if door is close before turning on the sauna

        Returns:
            A `HuumStatusResponse` from the Huum API
        """
        if temperature not in range(self.min_temp, self.max_temp):
            raise ValueError(
                f"Temperature '{temperature}' must be between {self.min_temp}-{self.max_temp}"
            )

        if not safety_override:
            await self._check_door()

        url = urljoin(API_BASE, "start")
        data = {"targetTemperature": temperature}

        response = await self.session.post(
            url, json=data, auth=self.auth, raise_for_status=True
        )
        json_data = await response.json()
        _LOGGER.debug("Received turn on response from HUUM API: %s", json_data)

        return HuumStatusResponse(**json_data)

    async def turn_off(self) -> HuumStatusResponse:
        """
        Turns off the sauna

        Returns:
            A `HuumStatusResponse` from the Huum API

        """
        url = urljoin(API_BASE, "stop")

        response = await self.session.post(url, auth=self.auth, raise_for_status=True)
        json_data = await response.json()
        _LOGGER.debug("Received turn off response from HUUM API: %s", json_data)

        return HuumStatusResponse(**json_data)

    async def set_temperature(
        self, temperature: int, safety_override: bool = False
    ) -> HuumStatusResponse:
        """
        Alias for turn_on as Huum does not expose an explicit "set_temperature" endpoint

        Implementation choice: Yes, aliasing can be done by simply asigning
        set_temperature = turn_on, however this will not create documentation,
        makes the code harder to read and is generally seen as non-pythonic.

        Args:
            temperature: Target temperature to set the sauna to
            safety_override: If False, check if door is close before turning on the sauna

        Returns:
            A `HuumStatusResponse` from the Huum API
        """
        return await self.turn_on(temperature, safety_override)

    async def status(self) -> HuumStatusResponse:
        """
        Get the status of the Sauna

        Returns:
            A `HuumStatusResponse` from the Huum API
        """
        url = urljoin(API_BASE, "status")

        response = await self.session.get(url, auth=self.auth, raise_for_status=True)
        json_data = await response.json()

        # Log the entire response data
        _LOGGER.debug("Received status response from HUUM API: %s", json_data)

        return HuumStatusResponse(**json_data)

    async def status_from_status_or_stop(self) -> HuumStatusResponse:
        """
        Get status from the status endpoint or from stop event if that is in option

        The Huum API does not return the target temperature if the sauna
        is not heating. Turning off the sauna will give the temperature,
        however. So if the sauna is not on, we can get the temperature
        set on the thermostat by telling it to turn off. If the sauna is on
        we get the target temperature from the status endpoint.

        Why this is not done in the status method is because there is an
        additional API call in the case that the status endpoint does not
        return target temperature. For this reason the status method is kept
        as a pure status request.

        Returns:
            A `HuumStatusResponse` from the Huum API
        """
        status_response = await self.status()
        if status_response.status == SaunaStatus.ONLINE_NOT_HEATING:
            status_response = await self.turn_off()
        return status_response

    async def open_session(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close_session(self) -> None:
        await self.session.close()

class SaunaStatus(IntEnum):
    OFFLINE = 230
    ONLINE_HEATING = 231
    ONLINE_NOT_HEATING = 232
    LOCKED = 233
    EMERGENCY_STOP = 400


STATUS_CODE_TEXTS: Dict[int, str] = {
    SaunaStatus.OFFLINE: "offline",
    SaunaStatus.ONLINE_HEATING: "online and heating",
    SaunaStatus.ONLINE_NOT_HEATING: "online but not heating",
    SaunaStatus.LOCKED: "being used by another user and is locked",
    SaunaStatus.EMERGENCY_STOP: "emergency stop",
}

CONFIG_CODE_TEXTS: Dict[int, str] = {
    1: "Configured to user light system",
    2: "Configured to use steamer system",
    3: "Configured to use both light and steamer systems",
}

STEAMER_CODE_TEXTS: Dict[int, str] = {
    1: "No water in steamer, steamer system not allowed to start"
}

class SafetyException(Exception):
    pass


class HuumStatus(BaseModel):
    code: int
    text: str


class HuumConfig(BaseModel):
    code: int
    text: str


class HuumSteamerError(BaseModel):
    code: int
    text: str
