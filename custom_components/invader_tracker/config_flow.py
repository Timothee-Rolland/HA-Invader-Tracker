"""Config flow for Invader Tracker integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import SelectOptionDict, SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .api.awazleon import AwazleonClient
from .api.flash_invader import FlashInvaderAPI
from .const import (
    CONF_API_INTERVAL,
    CONF_AWAZLEON_API_KEY,
    CONF_CITIES,
    CONF_NEW_CITY_DAYS,
    CONF_NEWS_DAYS,
    CONF_SCRAPE_INTERVAL,
    CONF_TRACK_FOLLOWED,
    CONF_UID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_NEW_CITY_DAYS,
    DEFAULT_NEWS_DAYS,
    DEFAULT_TRACK_FOLLOWED,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    MIN_UPDATE_INTERVAL_MINUTES,
)
from .exceptions import AuthenticationError, InvaderTrackerConnectionError

_LOGGER = logging.getLogger(__name__)

# UID validation pattern (UUID v4 format)
UID_PATTERN = re.compile(
    r"^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$",
    re.IGNORECASE,
)

# Predefined interval options: minutes (stored as str) -> display label
# SelectSelector requires string values; we convert to int on save.
INTERVAL_OPTIONS: dict[str, str] = {
    "15": "Every 15 minutes",
    "30": "Every 30 minutes",
    "60": "Every hour",
    "120": "Every 2 hours",
    "240": "Every 4 hours",
    "360": "Every 6 hours",
    "720": "Every 12 hours",
    "1440": "Daily",
    "10080": "Weekly",
    "43200": "Monthly",
}

# Sentinel value used to trigger the custom-interval step
_CUSTOM_SENTINEL = "0"

NEWS_DAYS_OPTIONS: dict[str, str] = {
    "7": "7 days",
    "14": "14 days",
    "30": "30 days",
    "60": "60 days",
    "90": "90 days",
    "180": "6 months",
    "365": "1 year",
}

NEW_CITY_DAYS_OPTIONS: dict[str, str] = {
    "3": "3 days",
    "7": "1 week",
    "14": "2 weeks",
    "30": "1 month",
}


def _select(options: dict[str, str], default: str) -> SelectSelector:
    """Build a dropdown SelectSelector from a {value: label} dict."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=v, label=label) for v, label in options.items()],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


def _interval_selector() -> SelectSelector:
    """Build the interval dropdown (predefined values + Custom…)."""
    opts = {**INTERVAL_OPTIONS, _CUSTOM_SENTINEL: "Custom…"}
    return _select(opts, "60")


def _interval_default(minutes: int) -> str:
    """Return the string value matching a stored interval (or sentinel)."""
    return str(minutes) if str(minutes) in INTERVAL_OPTIONS else _CUSTOM_SENTINEL


def _validate_uid(uid: str) -> bool:
    """Validate UID format."""
    if not uid:
        return False
    return bool(UID_PATTERN.match(uid.strip()))


def _custom_interval_schema(current: int) -> vol.Schema:
    """Build the custom interval free-text input schema."""
    return vol.Schema(
        {
            vol.Required(CONF_UPDATE_INTERVAL, default=current): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_UPDATE_INTERVAL_MINUTES),
            ),
        }
    )


class InvaderTrackerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for Invader Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._uid: str = ""
        self._awazleon_api_key: str = ""
        self._cities: dict[str, str] = {}
        self._pending_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> InvaderTrackerOptionsFlow:
        """Get the options flow for this handler."""
        return InvaderTrackerOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step - UID entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uid = user_input[CONF_UID].strip()

            if not _validate_uid(uid):
                errors["base"] = "invalid_uid_format"
            else:
                session = async_get_clientsession(self.hass)
                api = FlashInvaderAPI(session, uid)

                try:
                    await api.get_flashed_invaders()
                except AuthenticationError:
                    errors["base"] = "invalid_uid"
                except InvaderTrackerConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error validating UID")
                    errors["base"] = "unknown"

                if not errors:
                    self._uid = uid
                    return await self.async_step_awazleon_key()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_UID): str}),
            errors=errors,
        )

    async def async_step_awazleon_key(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the optional Awazleon API key step.

        Leaving the key blank disables Awazleon data entirely.
        """
        if user_input is not None:
            self._awazleon_api_key = (user_input.get(CONF_AWAZLEON_API_KEY) or "").strip()
            return await self.async_step_cities()

        return self.async_show_form(
            step_id="awazleon_key",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_AWAZLEON_API_KEY, default=""): str,
                }
            ),
        )

    async def async_step_cities(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle city selection + interval choice step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_cities = user_input.get(CONF_CITIES, [])

            if not selected_cities:
                errors["base"] = "no_cities_selected"
            else:
                cities = {code: self._cities.get(code, code) for code in selected_cities}
                chosen_val = user_input.get(CONF_UPDATE_INTERVAL, _CUSTOM_SENTINEL)

                self._pending_data = {
                    CONF_UID: self._uid,
                    CONF_AWAZLEON_API_KEY: self._awazleon_api_key,
                    CONF_CITIES: cities,
                }

                if chosen_val == _CUSTOM_SENTINEL:
                    return await self.async_step_custom_interval()

                self._pending_data[CONF_UPDATE_INTERVAL] = int(chosen_val)

                await self.async_set_unique_id(self._uid)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Invader Tracker",
                    data=self._pending_data,
                )

        # Fetch available cities from awazleon (only if an API key was provided)
        if self._awazleon_api_key:
            session = async_get_clientsession(self.hass)
            awazleon = AwazleonClient(session, self._awazleon_api_key)
            try:
                cities_list = await awazleon.get_cities()
                self._cities = {c.code: c.name for c in cities_list}
            except Exception:
                _LOGGER.exception("Unexpected error fetching cities")
                errors["base"] = "cannot_connect_spotter"
                self._cities = {}

            if not self._cities and not errors:
                errors["base"] = "no_cities_found"

        city_options = dict(sorted(self._cities.items(), key=lambda x: x[1]))

        return self.async_show_form(
            step_id="cities",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CITIES): cv.multi_select(city_options),
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=_interval_default(DEFAULT_UPDATE_INTERVAL_MINUTES),
                    ): _interval_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_custom_interval(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle custom interval entry (config flow)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            minutes = user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES)
            self._pending_data[CONF_UPDATE_INTERVAL] = int(minutes)

            await self.async_set_unique_id(self._uid)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Invader Tracker",
                data=self._pending_data,
            )

        return self.async_show_form(
            step_id="custom_interval",
            data_schema=_custom_interval_schema(DEFAULT_UPDATE_INTERVAL_MINUTES),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle reauthorization."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uid = user_input[CONF_UID].strip()

            if not _validate_uid(uid):
                errors["base"] = "invalid_uid_format"
            else:
                session = async_get_clientsession(self.hass)
                api = FlashInvaderAPI(session, uid)

                try:
                    await api.get_flashed_invaders()
                except AuthenticationError:
                    errors["base"] = "invalid_uid"
                except InvaderTrackerConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    errors["base"] = "unknown"

                if not errors:
                    existing_entry = await self.async_set_unique_id(uid)
                    if existing_entry:
                        self.hass.config_entries.async_update_entry(
                            existing_entry,
                            data={**existing_entry.data, CONF_UID: uid},
                        )
                        await self.hass.config_entries.async_reload(existing_entry.entry_id)
                        return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_UID): str}),
            errors=errors,
        )


class InvaderTrackerOptionsFlow(OptionsFlow):
    """Handle options flow for Invader Tracker."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._cities: dict[str, str] = {}
        self._pending_options: dict[str, Any] = {}

    def _get_current_cities(self) -> dict[str, str]:
        """Get currently configured cities (options override data)."""
        return self._config_entry.options.get(CONF_CITIES) or self._config_entry.data.get(CONF_CITIES, {})

    def _get_current_value(self, key: str, default: Any) -> Any:
        """Get current config value (options override data)."""
        return self._config_entry.options.get(key, self._config_entry.data.get(key, default))

    def _get_current_interval(self) -> int:
        """Return current update interval in minutes, migrating legacy values."""
        # New key takes precedence
        if CONF_UPDATE_INTERVAL in self._config_entry.options:
            return int(self._config_entry.options[CONF_UPDATE_INTERVAL])
        if CONF_UPDATE_INTERVAL in self._config_entry.data:
            return int(self._config_entry.data[CONF_UPDATE_INTERVAL])
        # Migrate from legacy scrape_interval (hours) — take the smaller of the two
        scrape_h = self._config_entry.options.get(
            CONF_SCRAPE_INTERVAL,
            self._config_entry.data.get(CONF_SCRAPE_INTERVAL, 24),
        )
        api_h = self._config_entry.options.get(
            CONF_API_INTERVAL,
            self._config_entry.data.get(CONF_API_INTERVAL, 1),
        )
        return min(int(scrape_h), int(api_h)) * 60

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow - city selection and interval."""
        errors: dict[str, str] = {}

        if user_input is not None:
            uid = (user_input.get(CONF_UID) or "").strip()
            selected_cities = user_input.get(CONF_CITIES, [])

            if not _validate_uid(uid):
                errors[CONF_UID] = "invalid_uid_format"
            elif not selected_cities:
                errors["base"] = "no_cities_selected"
            else:
                current_uid = self._config_entry.data.get(CONF_UID, "")
                if uid.upper() != current_uid.upper():
                    session = async_get_clientsession(self.hass)
                    api = FlashInvaderAPI(session, uid)
                    try:
                        await api.get_flashed_invaders()
                    except AuthenticationError:
                        errors[CONF_UID] = "invalid_uid"
                    except InvaderTrackerConnectionError:
                        errors[CONF_UID] = "cannot_connect"
                    except Exception:
                        _LOGGER.exception("Unexpected error validating UID")
                        errors[CONF_UID] = "unknown"

                if not errors:
                    cities = {code: self._cities.get(code, code) for code in selected_cities}
                    chosen_val = user_input.get(CONF_UPDATE_INTERVAL, _CUSTOM_SENTINEL)
                    # news_days and new_city_days are stored as str from SelectSelector → convert to int
                    news_val = user_input.get(CONF_NEWS_DAYS, str(DEFAULT_NEWS_DAYS))
                    new_city_val = user_input.get(CONF_NEW_CITY_DAYS, str(DEFAULT_NEW_CITY_DAYS))

                    api_key = (user_input.get(CONF_AWAZLEON_API_KEY) or "").strip()
                    self._pending_options = {
                        CONF_CITIES: cities,
                        CONF_AWAZLEON_API_KEY: api_key,
                        CONF_NEWS_DAYS: int(news_val),
                        CONF_NEW_CITY_DAYS: int(new_city_val),
                        CONF_TRACK_FOLLOWED: user_input.get(
                            CONF_TRACK_FOLLOWED,
                            self._get_current_value(CONF_TRACK_FOLLOWED, DEFAULT_TRACK_FOLLOWED),
                        ),
                    }

                    if uid.upper() != current_uid.upper():
                        self.hass.config_entries.async_update_entry(
                            self._config_entry,
                            unique_id=uid.upper(),
                            data={**self._config_entry.data, CONF_UID: uid},
                        )

                    if chosen_val == _CUSTOM_SENTINEL:
                        return await self.async_step_custom_interval()

                    self._pending_options[CONF_UPDATE_INTERVAL] = int(chosen_val)
                    return self.async_create_entry(title="", data=self._pending_options)

        # Fetch available cities from awazleon (only if an API key is configured)
        current_api_key = self._get_current_value(CONF_AWAZLEON_API_KEY, "")
        if current_api_key:
            session = async_get_clientsession(self.hass)
            awazleon = AwazleonClient(session, current_api_key)
            try:
                cities_list = await awazleon.get_cities()
                self._cities = {c.code: c.name for c in cities_list}
            except Exception:
                _LOGGER.exception("Error fetching cities for options")
                self._cities = self._get_current_cities()
        else:
            self._cities = self._get_current_cities()

        current_cities = list(self._get_current_cities().keys())
        current_interval = self._get_current_interval()
        current_news_days = self._get_current_value(CONF_NEWS_DAYS, DEFAULT_NEWS_DAYS)
        current_new_city_days = self._get_current_value(CONF_NEW_CITY_DAYS, DEFAULT_NEW_CITY_DAYS)
        city_options = dict(sorted(self._cities.items(), key=lambda x: x[1]))

        current_uid = self._config_entry.data.get(CONF_UID, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UID, default=current_uid): str,
                    vol.Required(CONF_CITIES, default=current_cities): cv.multi_select(city_options),
                    vol.Optional(
                        CONF_AWAZLEON_API_KEY,
                        default=self._get_current_value(CONF_AWAZLEON_API_KEY, ""),
                    ): str,
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=_interval_default(current_interval),
                    ): _interval_selector(),
                    vol.Optional(
                        CONF_NEWS_DAYS,
                        default=str(current_news_days),
                    ): _select(NEWS_DAYS_OPTIONS, str(DEFAULT_NEWS_DAYS)),
                    vol.Optional(
                        CONF_NEW_CITY_DAYS,
                        default=str(current_new_city_days),
                    ): _select(NEW_CITY_DAYS_OPTIONS, str(DEFAULT_NEW_CITY_DAYS)),
                    vol.Optional(
                        CONF_TRACK_FOLLOWED,
                        default=self._get_current_value(CONF_TRACK_FOLLOWED, DEFAULT_TRACK_FOLLOWED),
                    ): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_custom_interval(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle custom interval entry (options flow)."""
        errors: dict[str, str] = {}
        current_interval = self._get_current_interval()

        if user_input is not None:
            minutes = user_input.get(CONF_UPDATE_INTERVAL, current_interval)
            self._pending_options[CONF_UPDATE_INTERVAL] = int(minutes)
            return self.async_create_entry(title="", data=self._pending_options)

        return self.async_show_form(
            step_id="custom_interval",
            data_schema=_custom_interval_schema(
                current_interval if current_interval >= MIN_UPDATE_INTERVAL_MINUTES else DEFAULT_UPDATE_INTERVAL_MINUTES
            ),
            errors=errors,
        )
