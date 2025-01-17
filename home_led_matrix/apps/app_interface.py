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

