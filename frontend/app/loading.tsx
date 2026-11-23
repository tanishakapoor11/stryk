import { BallLoader } from "@/components/ui/ball-loader";

export default function Loading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center px-4">
      <BallLoader label="Counting the deliveries" size={112} />
    </div>
  );
}
