from pydantic import BaseModel


class HooksMixin(BaseModel):
    def pre_py2v_hook(self) -> None:
        pass

    def post_py2v_hook(self) -> None:
        pass
