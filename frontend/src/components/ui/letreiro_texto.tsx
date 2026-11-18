import { useEffect, useState } from "react";


export function useTypewriter(text, speed = 80, delay = 1000) {
  const [output, setOutput] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [i, setI] = useState(0);

  useEffect(() => {
    let timeout;

    const handleTyping = () => {
      if (!isDeleting) {
        if (i < text.length) {
          setOutput(text.substring(0, i + 1));
          setI(i + 1);
          timeout = setTimeout(handleTyping, speed);
        } else {
          timeout = setTimeout(() => setIsDeleting(true), delay);
        }
      } else {
        if (i > 0) {
          setOutput(text.substring(0, i - 1));
          setI(i - 1);
          timeout = setTimeout(handleTyping, speed / 1.5);
        } else {
          setIsDeleting(false);
          timeout = setTimeout(handleTyping, speed);
        }
      }
    };

    timeout = setTimeout(handleTyping, speed);
    return () => clearTimeout(timeout);
  }, [i, isDeleting, text, speed, delay]);

  return output;
}
