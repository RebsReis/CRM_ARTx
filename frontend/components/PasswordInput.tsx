"use client";

import { useState, type ComponentProps } from "react";

export default function PasswordInput(props: Omit<ComponentProps<"input">, "type">) {
  const [visivel, setVisivel] = useState(false);
  return <span className="auth-password">
    <input {...props} type={visivel ? "text" : "password"}/>
    <button type="button" className="auth-password-toggle" aria-label={visivel ? "Ocultar senha" : "Mostrar senha"} aria-pressed={visivel} onClick={() => setVisivel((valor) => !valor)}>{visivel ? "Ocultar" : "Mostrar"}</button>
  </span>;
}
