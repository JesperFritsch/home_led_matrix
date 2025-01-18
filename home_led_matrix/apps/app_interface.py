from abc import ABC, abstractmethod

class IAsyncApp(ABC):
    """Interface for an asynchronous app."""
    @abstractmethod
    async def run(self):
        """Run the app."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the app."""
        pass

    @abstractmethod
    async def pause(self):
        """Pause the app."""
        pass

    @abstractmethod
    async def resume(self):
        """Resume the app."""
        pass

    @abstractmethod
    async def redraw(self):
        """Redraw the app."""
        pass

    @abstractmethod
    async def is_running(self):
        """Return if the app is running."""
        pass

