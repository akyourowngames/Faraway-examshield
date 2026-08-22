"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { usePrefersReducedMotion } from "@/lib/use-prefers-reduced-motion";

export function FadeIn({ children, ...props }: HTMLMotionProps<"div">) {
  const reduce = usePrefersReducedMotion();

  if (reduce) {
    return (
      <motion.div
        initial={false}
        animate={{ opacity: 1 }}
        transition={{ duration: 0 }}
        {...props}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
