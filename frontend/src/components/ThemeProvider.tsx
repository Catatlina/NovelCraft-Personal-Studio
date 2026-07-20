import { createContext, useContext, useState } from 'react';
const ThemeContext = createContext<any>({});
export const useTheme = () => useContext(ThemeContext);
export function ThemeProvider(p: any) {
    const [theme, setTheme] = useState('dark');
    return <ThemeContext.Provider value={{ theme, setTheme }}>{p.children}</ThemeContext.Provider>;
}
