import { cn } from '@/lib/utils';
import Image from 'next/image';

interface AvatarProps {
  src?: string;
  name: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeMap = {
  sm: { container: 'w-[22px] h-[22px]', text: 'text-[8px]', px: 22 },
  md: { container: 'w-[30px] h-[30px]', text: 'text-[11px]', px: 30 },
  lg: { container: 'w-[40px] h-[40px]', text: 'text-[14px]', px: 40 },
};

export function Avatar({ src, name, size = 'md', className }: AvatarProps) {
  const initials = name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  const s = sizeMap[size];

  if (src) {
    return (
      <Image
        src={src}
        alt={name}
        width={s.px}
        height={s.px}
        className={cn('rounded-full object-cover', s.container, className)}
      />
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center justify-center rounded-full font-display font-semibold',
        'bg-accent-subtle text-accent',
        s.container, s.text, className
      )}
    >
      {initials}
    </span>
  );
}
