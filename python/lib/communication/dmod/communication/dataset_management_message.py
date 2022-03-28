from .message import AbstractInitRequest, MessageEventType, Response
from dmod.core.meta_data import DataCategory, DataDomain
from numbers import Number
from enum import Enum
from typing import Dict, Optional, Union


class ManagementAction(Enum):
    """
    Type enumerating the standard actions that can be requested via ::class:`DatasetManagementMessage`.
    """
    UNKNOWN = (-1, False, False)
    """ Placeholder action for when actual action is not known, generally representing an error (e.g., bad parsing). """
    CREATE = (1, True, True)
    """ Dataset creation action. """
    ADD_DATA = (2, True, False)
    """ Addition of data to an existing dataset. """
    REMOVE_DATA = (3, True, False)
    """ Removal of data from an existing dataset. """
    DELETE = (4, True, False)
    """ Deletion of an existing dataset. """
    SEARCH = (5, False, True)
    """ Search for dataset(s) satisfying certain conditions (e.g., AORC forcings for right times and catchments). """
    QUERY = (6, True, False)
    """ Query for information about a dataset (e.g., what time period and catchments does a forcing dataset cover). """
    CLOSE_AWAITING = (7, False, False)
    """ Action to close an ongoing, multi-message dialog. """

    @classmethod
    def get_for_name(cls, name_str: str) -> 'ManagementAction':
        """
        Get the enum value corresponding to the given string, ignoring case, and defaulting to ``UNKNOWN``.

        Parameters
        ----------
        name_str : str
            Expected string representation of one of the enum values.

        Returns
        -------
        ManagementAction
            Enum value corresponding to the given string, or ``UNKNOWN`` if correspondence could not be determined.
        """
        cleaned_up_str = name_str.strip().upper()
        for value in cls:
            if value.name.upper() == cleaned_up_str:
                return value
        return cls.UNKNOWN

    def __init__(self, uid: int, requires_name: bool, requires_category: bool):
        self._uid = uid
        self._requires_name = requires_name
        self._requires_category = requires_category

    @property
    def requires_data_category(self) -> bool:
        """
        Whether this type of action requires a data category in order for the action to be valid.

        Returns
        -------
        bool
            Whether this type of action requires a data category in order for the action to be valid.

        See Also
        -------
        ::method:`requires_dataset_name`
        """
        return self._requires_category

    @property
    def requires_dataset_name(self) -> bool:
        """
        Whether this type of action requires a dataset name in order for the action to be valid.

        Certain actions - e.g., ``CREATE`` - cannot be performed without the name of the dataset involved. However,
        others, such as ``SEARCH``, inherently do not.

        This property provides a convenient way of accessing whether a name is required for a particular enum value's
        action to be performable.

        Returns
        -------
        bool
            Whether this type of action requires a dataset name in order for the action to be valid.
        """
        return self._requires_name


class DatasetManagementMessage(AbstractInitRequest):
    """
    Message type for initiating any action related to dataset management.

    Valid actions are enumerated by the ::class:`ManagementAction`.
    """

    event_type: MessageEventType = MessageEventType.DATASET_MANAGEMENT

    _SERIAL_KEY_ACTION = 'action'
    _SERIAL_KEY_CATEGORY = 'category'
    _SERIAL_KEY_DATA = 'data'
    _SERIAL_KEY_DATA_DOMAIN = 'data_domain'
    _SERIAL_KEY_DATA_LOCATION = 'data_location'
    _SERIAL_KEY_DATASET_NAME = 'dataset_name'
    _SERIAL_KEY_IS_PENDING_DATA = 'pending_data'
    _SERIAL_KEY_IS_READ_ONLY = 'read_only'

    @classmethod
    def factory_init_from_deserialized_json(cls, json_obj: dict) -> Optional['DatasetManagementMessage']:
        dataset_name = json_obj[cls._SERIAL_KEY_DATASET_NAME] if cls._SERIAL_KEY_DATASET_NAME in json_obj else None
        category = json_obj[cls._SERIAL_KEY_CATEGORY] if cls._SERIAL_KEY_CATEGORY in json_obj else None
        raw_data = json_obj[cls._SERIAL_KEY_DATA] if cls._SERIAL_KEY_DATA in json_obj else None
        data_loc = json_obj[cls._SERIAL_KEY_DATA_LOCATION] if cls._SERIAL_KEY_DATA_LOCATION in json_obj else None

        try:
            obj = cls(action=json_obj[cls._SERIAL_KEY_ACTION], dataset_name=dataset_name, category=category,
                      data=raw_data, is_read_only_dataset=json_obj[cls._SERIAL_KEY_IS_READ_ONLY],
                      data_location=data_loc, is_pending_data=json_obj[cls._SERIAL_KEY_IS_PENDING_DATA])
            if cls._SERIAL_KEY_DATA_DOMAIN in json_obj:
                obj.data_domain = DataDomain.factory_init_from_deserialized_json(json_obj[cls._SERIAL_KEY_DATA_DOMAIN])
            return obj
        except Exception as e:
            return None

    def __init__(self, action: ManagementAction, dataset_name: Optional[str] = None, is_read_only_dataset: bool = False,
                 category: Optional[DataCategory] = None, data: Optional[bytes] = None,
                 data_location: Optional[str] = None, is_pending_data: bool = False):
        """
        Initialize this instance.

        Parameters
        ----------
        action : ManagementAction
            The action this message embodies or requests.
        dataset_name : Optional[str]
            The optional name of the involved dataset, when applicable; defaults to ``None``.
        is_read_only_dataset : bool
            Whether dataset involved is, should be, or must be (depending on action) read-only; defaults to ``False``.
        category : Optional[str]
            The optional category of the involved dataset or datasets, when applicable; defaults to ``None``.
        data : Optional[bytes]
            Optional encoded byte string containing data to insert into the dataset.
        data_location : Optional[str]
            Optional location/file/object/etc. for acted-upon data.
        is_pending_data : bool
            Whether the message sender has more data not included within this message, but that the sender will want to
            send in a subsequent message.
        """
        # Sanity check certain param values depending on the action; e.g., can't CREATE a dataset without a name
        err_msg_template = "Cannot create {} for action {} without {}"
        if dataset_name is None and action.requires_dataset_name:
            raise RuntimeError(err_msg_template.format(self.__class__.__name__, action, "a dataset name"))
        if category is None and action.requires_data_category:
            raise RuntimeError(err_msg_template.format(self.__class__.__name__, action, "a data category"))

        # TODO: raise exceptions for actions for which the workflow is not yet supported (e.g., REMOVE_DATA)

        self._action = action
        self._dataset_name = dataset_name
        self._is_read_only_dataset = is_read_only_dataset
        self._category = category
        self._domain = None
        self._data = data
        self._data_location = data_location
        self._is_pending_data = is_pending_data

    @property
    def data(self) -> Optional[bytes]:
        """
        Optional byte string containing raw data to be added to a dataset.

        Returns
        -------
        Optional[bytes]
            Byte string of raw data to be added to a dataset.
        """
        return self._data

    @property
    def data_location(self) -> Optional[str]:
        """
        Location for acted-upon data.

        Returns
        -------
        Optional[str]
            Location for acted-upon data.
        """
        return self._data_location

    @property
    def is_pending_data(self) -> bool:
        """
        Whether there is additional data the sender has beyond what is included in this message.

        The implication when this is ``True`` is that, after this message is handled and responded to, the sender will
        want to send at least one additional message to transmit further data.

        Returns
        -------
        bool
            Whether there is additional data the sender has beyond what is included in this message.
        """
        return self._is_pending_data

    @property
    def data_category(self) -> Optional[DataCategory]:
        """
        The category of the involved data, if applicable.

        Returns
        -------
        bool
            The category of the involved data, if applicable.
        """
        return self._category

    @property
    def data_domain(self) -> Optional[DataDomain]:
        """
        The domain of the involved data, if applicable.

        Returns
        -------
        Optional[DataDomain]
            The domain of the involved data, if applicable.
        """
        return self._domain

    @data_domain.setter
    def data_domain(self, domain: DataDomain):
        self._domain = domain

    @property
    def dataset_name(self) -> Optional[str]:
        """
        The name of the involved dataset, if applicable.

        Returns
        -------
        Optional
            The name of the involved dataset, if applicable.
        """
        return self._dataset_name

    @property
    def is_read_only_dataset(self) -> bool:
        """
        Whether the dataset involved is, should be, or must be (depending on action) read-only.

        Returns
        -------
        bool
            Whether the dataset involved is, should be, or must be (depending on action) read-only.
        """
        return self._is_read_only_dataset

    @property
    def management_action(self) -> ManagementAction:
        """
        The type of ::class:`ManagementAction` this message embodies or requests.

        Returns
        -------
        ManagementAction
            The type of ::class:`ManagementAction` this message embodies or requests.
        """
        return self._action

    def to_dict(self) -> Dict[str, Union[str, Number, dict, list]]:
        serial = {self._SERIAL_KEY_ACTION: self.management_action,
                  self._SERIAL_KEY_CATEGORY: self.data_category,
                  self._SERIAL_KEY_IS_READ_ONLY: self.is_read_only_dataset,
                  self._SERIAL_KEY_IS_PENDING_DATA: self.is_pending_data}
        if self.dataset_name is not None:
            serial[self._SERIAL_KEY_DATASET_NAME] = self.dataset_name
        if self.data_category is not None:
            serial[self._SERIAL_KEY_CATEGORY] = self.data_category
        if self.data is not None:
            serial[self._SERIAL_KEY_DATA] = self.data
        if self.data_location is not None:
            serial[self._SERIAL_KEY_DATA_LOCATION] = self.data_location
        if self.data_domain is not None:
            serial[self._SERIAL_KEY_DATA_DOMAIN] = self.data_domain.to_dict()
        return serial


class DatasetManagementResponse(Response):

    _DATA_KEY_ACTION= 'action'
    _DATA_KEY_DATA_ID = 'data_id'
    _DATA_KEY_DATASET_NAME = 'dataset_name'
    _DATA_KEY_IS_AWAITING = 'is_awaiting'
    response_to_type = DatasetManagementMessage

    @classmethod
    def factory_create(cls, action: ManagementAction, success: bool, reason: str, message: str = '',
                       data: Optional[dict] = None, is_awaiting: bool = False, dataset_name: Optional[str] = None,
                       data_id: Optional[str] = None) -> 'DatasetManagementResponse':
        """
        Factory create method to simplify init while maintaining standard structure of ::method:`__init__`.

        Parameters
        ----------
        action
        success
        reason
        message
        data
        is_awaiting
        dataset_name
        data_id

        Returns
        -------
        DatasetManagementResponse
            A newly initialized instance.
        """
        if data is None:
            data = {}

        data[cls._DATA_KEY_ACTION] = action
        data[cls._DATA_KEY_IS_AWAITING] = is_awaiting

        if data_id is not None:
            data[cls._DATA_KEY_DATA_ID] = data_id

        if dataset_name is not None:
            data[cls._DATA_KEY_DATASET_NAME] = dataset_name

        return cls(success=success, reason=reason, message=message, data=data)

    def __init__(self, success: bool, reason: str, message: str = '', data: Optional[dict] = None):
        if data is None:
            data = {self._DATA_KEY_IS_AWAITING: False}
        elif self._DATA_KEY_IS_AWAITING not in data:
            data[self._DATA_KEY_IS_AWAITING] = False
        super().__init__(success=success, reason=reason, message=message, data=data)

    @property
    def action(self) -> ManagementAction:
        """
        The action requested by the ::class:`DatasetManagementMessage` for which this instance is the response.

        Returns
        -------
        ManagementAction
            The action requested by the ::class:`DatasetManagementMessage` for which this instance is the response.
        """
        return self.data[self._DATA_KEY_ACTION]

    @property
    def data_id(self) -> Optional[str]:
        """
        When available, the 'data_id' of the related dataset.

        Returns
        -------
        Optional[str]
            When available, the 'data_id' of the related dataset.
        """
        return self.data[self._DATA_KEY_DATA_ID] if self._DATA_KEY_DATA_ID in self.data else None

    @property
    def dataset_name(self) -> Optional[str]:
        """
        When available, the name of the relevant dataset.

        Returns
        -------
        Optional[str]
            When available, the name of the relevant dataset; otherwise ``None``.
        """
        return self.data[self._DATA_KEY_DATASET_NAME] if self._DATA_KEY_DATASET_NAME in self.data else None

    @property
    def is_awaiting(self) -> bool:
        """
        Whether the response, in addition to success, indicates the response sender is awaiting something additional.

        Typically, this is an indication that the responder side is ready and expecting additional follow-up messages
        from the originator.  For example, after responding to a successful ``CREATE``, a message may set that it is
        in the awaiting state to wait for data to be uploaded by the originator for insertion into the new dataset.

        Returns
        -------
        bool
            Whether the response indicates the response sender is awaiting something additional.
        """
        return self.data[self._DATA_KEY_IS_AWAITING]

