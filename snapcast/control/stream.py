class Snapstream:
    """
    Represents a snapcast stream.

    Attributes:
        identifier (str): The stream id.
        status (str): The stream status.
        name (str): The stream name.
        friendly_name (str): The friendly name of the stream.
        metadata (dict): The metadata of the stream.
        properties (dict): The properties of the stream.
        path (str): The stream path.

    Methods:
        __init__(data): Initializes the Snapstream object.
        update(data): Updates the stream data.
        update_meta(data): Updates the stream metadata.
        update_metadata(data): Updates the stream metadata.
        update_properties(data): Updates the stream properties.
        callback(): Runs the callback function.
        set_callback(func): Sets the callback function.
    """

    def __init__(self, data):
        """
        Initialize the Stream object.

        Args:
            data (dict): A dictionary containing the initial data for the Stream.

        """
        self.update(data)
        self._callback_func = None

    @property
    def identifier(self):
        """
        Get stream id.

        Returns:
            str: The stream id.
        """
        return self._stream.get("id")

    @property
    def status(self):
        """
        Get stream status.

        Returns:
            The status of the stream.
        """
        return self._stream.get("status")

    @property
    def name(self):
        """
        Get stream name.

        Returns:
            str: The name of the stream.
        """
        return self._stream.get("uri").get("query").get("name")

    @property
    def friendly_name(self):
        """
        Get friendly name.

        Returns:
            str: The friendly name of the stream. If the name is empty, the identifier is returned instead.
        """
        return self.name if self.name != "" else self.identifier

    @property
    def metadata(self):
        """Get metadata.

        Returns:
            The metadata of the stream, if available. Otherwise, returns None.
        """
        if "properties" in self._stream:
            return self._stream["properties"].get("metadata")
        return self._stream.get("meta")

    @property
    def meta(self):
        """Get metadata. Deprecated."""
        return self.metadata

    @property
    def properties(self):
        """
        Get properties.

        Returns:
            dict: The properties of the stream.
        """
        return self._stream.get("properties")

    @property
    def path(self):
        """
        Get stream path.

        Returns:
            str: The path of the stream URI.

        """
        return self._stream.get("uri").get("path")

    def update(self, data):
        """
        Update stream.

        Args:
            data: The updated data for the stream.

        """
        self._stream = data

    def update_meta(self, data):
        """
        Update stream metadata.

        Args:
            data (dict): A dictionary containing the updated metadata.
        """
        self.update_metadata(data)

    def update_metadata(self, data):
        """
        Update stream metadata.

        Args:
            data (dict): The updated metadata for the stream.

        """
        if "properties" in self._stream:
            self._stream["properties"]["metadata"] = data
        self._stream["meta"] = data

    def update_properties(self, data):
        """
        Update stream properties.

        Args:
            data (dict): A dictionary containing the updated properties of the stream.
        """
        self._stream["properties"] = data

    def __repr__(self):
        """Return string representation of the Snapstream object."""
        return f"Snapstream ({self.name})"

    def callback(self):
        """Run callback.

        This method executes the callback function, if it exists and is callable.
        It passes the current instance of the class as an argument to the callback function.
        """
        if self._callback_func and callable(self._callback_func):
            self._callback_func(self)

    def set_callback(self, func):
        """
        Set callback.

        Args:
            func (callable): The callback function to be set.

        """
        self._callback_func = func
