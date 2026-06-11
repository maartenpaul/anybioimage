import { useEffect, useState } from 'react';

export function useModelTrait(model, name) {
  const [value, setValue] = useState(() => model.get(name));
  useEffect(() => {
    const handler = () => setValue(model.get(name));
    model.on(`change:${name}`, handler);
    return () => model.off(`change:${name}`, handler);
  }, [model, name]);
  return value;
}
