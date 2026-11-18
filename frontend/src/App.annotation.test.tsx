// @vitest-environment jsdom

import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AnnotationView } from "./App";
import type { Annotation, ClassLabel, Dataset, ImageItem } from "./types";

vi.mock("./annotation/AnnotationCanvas", () => ({
  AnnotationCanvas: ({ onChange }: { onChange: (drafts: unknown[]) => void }) => (
    <button onClick={() => onChange([{ id: "ann-1", class_id: "cls-1", type: "obb", obb: { cx: 50, cy: 40, width: 60, height: 40, angle: 45 }, source: "manual" }])}>
      模拟旋转 OBB
    </button>
  ),
}));

const dataset: Dataset = { id: "ds-1", name: "vehicles", description: null, task_type: "obb", image_count: 1, annotated_image_count: 1, class_count: 1, created_at: "", updated_at: "" };
const image: ImageItem = { id: "img-1", dataset_id: dataset.id, file_name: "vehicle.png", width: 100, height: 80, split: "train", status: "annotated", file_url: "/api/images/img-1/file", created_at: "", updated_at: "" };
const secondImage: ImageItem = { ...image, id: "img-2", file_name: "vehicle-02.png", status: "unannotated" };
const classes: ClassLabel[] = [{ id: "cls-1", dataset_id: dataset.id, class_index: 0, name: "vehicle", color: "#22c55e", created_at: "", updated_at: "" }];
const personClass: ClassLabel = { id: "cls-2", dataset_id: dataset.id, class_index: 1, name: "person", color: "#3157d5", created_at: "", updated_at: "" };
const annotation: Annotation = { id: "ann-1", image_id: image.id, dataset_id: dataset.id, class_id: "cls-1", class_index: 0, label: "vehicle", color: "#22c55e", type: "obb", bbox: null, polygon: null, obb: { cx: 45, cy: 35, width: 30, height: 20, angle: 20 }, source: "manual", created_at: "", updated_at: "" };

let root: Root | undefined;
let container: HTMLDivElement | undefined;

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => {
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});

afterEach(() => {
  act(() => root?.unmount());
  container?.remove();
});

describe("AnnotationView persistence", () => {
  it("shows the complete image list and switches the active image", () => {
    const onImageSelect = vi.fn();
    act(() => {
      root?.render(<AnnotationView dataset={dataset} image={image} images={[image, secondImage]} onImageSelect={onImageSelect} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    expect(container?.textContent).toContain("2 张图片");
    expect(container?.textContent).toContain("vehicle-02.png");
    expect(container?.textContent).toContain("未标注");
    const item = Array.from(container?.querySelectorAll<HTMLButtonElement>(".annotation-image-select") ?? []).find((button) => button.textContent?.includes("vehicle-02.png"));
    act(() => item?.click());
    expect(onImageSelect).toHaveBeenCalledWith(secondImage);
  });

  it("paginates the image list at twenty items", () => {
    const images = [image, ...Array.from({ length: 20 }, (_, index) => ({ ...image, id: `img-${index + 2}`, file_name: `vehicle-${index + 2}.png` }))];
    act(() => {
      root?.render(<AnnotationView dataset={{ ...dataset, image_count: images.length }} image={image} images={images} onImageSelect={vi.fn()} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    expect(container?.querySelectorAll(".annotation-image-item")).toHaveLength(20);
    expect(container?.textContent).toContain("第 1 / 2 页");
    const next = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((button) => button.textContent === "下一页");
    act(() => next?.click());
    expect(container?.querySelectorAll(".annotation-image-item")).toHaveLength(1);
    expect(container?.textContent).toContain("vehicle-21.png");
  });

  it("filters the image list by train, val and test split", () => {
    const valImage = { ...secondImage, split: "val" as const };
    const testImage = { ...image, id: "img-3", file_name: "vehicle-03.png", split: "test" as const };
    act(() => {
      root?.render(<AnnotationView dataset={{ ...dataset, image_count: 3 }} image={image} images={[image, valImage, testImage]} onImageSelect={vi.fn()} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    expect(container?.querySelectorAll(".annotation-image-item")).toHaveLength(3);
    const valTab = container?.querySelector<HTMLButtonElement>(".annotation-image-split-tabs button:nth-child(3)");
    act(() => valTab?.click());

    expect(container?.querySelectorAll(".annotation-image-item")).toHaveLength(1);
    expect(container?.textContent).toContain("vehicle-02.png");
    expect(container?.textContent).not.toContain("vehicle-03.png");
  });

  it("saves the edited OBB draft without its client-only id", () => {
    const onSave = vi.fn();
    act(() => {
      root?.render(<AnnotationView dataset={dataset} image={image} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={onSave} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const rotate = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((item) => item.textContent === "模拟旋转 OBB");
    act(() => rotate?.click());
    const save = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((item) => item.textContent === "保存标注");
    act(() => save?.click());

    expect(onSave).toHaveBeenCalledWith([
      { id: "ann-1", class_id: "cls-1", type: "obb", obb: { cx: 50, cy: 40, width: 60, height: 40, angle: 45 }, source: "manual" },
    ]);
  });

  it("shows unsaved state after a draft changes", () => {
    const onDirtyChange = vi.fn();
    act(() => {
      root?.render(<AnnotationView dataset={dataset} image={image} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onDirtyChange={onDirtyChange} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const rotate = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((item) => item.textContent === "模拟旋转 OBB");
    act(() => rotate?.click());

    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    expect(container?.textContent).toContain("未保存修改");
  });

  it("deletes one annotation from the list before saving", () => {
    const onSave = vi.fn();
    act(() => {
      root?.render(<AnnotationView dataset={dataset} image={image} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={onSave} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const deleteButton = container?.querySelector<HTMLButtonElement>("button[aria-label='删除标注 1']");
    expect(deleteButton).toBeTruthy();
    act(() => deleteButton?.click());
    const save = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((item) => item.textContent === "保存标注");
    act(() => save?.click());

    expect(onSave).toHaveBeenCalledWith([]);
  });

  it("deletes the selected annotation with Delete", () => {
    const onSave = vi.fn();
    act(() => {
      root?.render(<AnnotationView dataset={dataset} image={image} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={onSave} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const row = container?.querySelector<HTMLDivElement>(".shape-row");
    act(() => row?.click());
    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete" })));
    const save = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((item) => item.textContent === "保存标注");
    act(() => save?.click());

    expect(onSave).toHaveBeenCalledWith([]);
  });

  it("keeps previous and next navigation available by button and keyboard", () => {
    const onPrevious = vi.fn();
    const onNext = vi.fn();
    act(() => {
      root?.render(<AnnotationView dataset={{ ...dataset, image_count: 2 }} image={image} images={[image, secondImage]} onImageSelect={vi.fn()} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onPrevious={onPrevious} onNext={onNext} hasPrevious hasNext onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const previous = container?.querySelector<HTMLButtonElement>(".annotation-navigation button:first-child");
    const next = container?.querySelector<HTMLButtonElement>(".annotation-navigation button:last-child");
    expect(previous?.textContent).toContain("上一张");
    expect(next?.textContent).toContain("下一张");
    act(() => next?.click());
    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft" })));
    expect(onNext).toHaveBeenCalledTimes(1);
    expect(onPrevious).toHaveBeenCalledTimes(1);
  });

  it("adds a custom class from the annotation sidebar", async () => {
    const onCreateClass = vi.fn(async () => personClass);
    act(() => {
      root?.render(<AnnotationView dataset={dataset} image={image} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onCreateClass={onCreateClass} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const open = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((button) => button.textContent?.includes("新增类别"));
    act(() => open?.click());
    const input = container?.querySelector<HTMLInputElement>("input[placeholder='例如：person']");
    expect(input).toBeTruthy();
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    act(() => {
      setValue?.call(input, "person");
      input?.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const form = container?.querySelector<HTMLFormElement>(".annotation-class-form");
    await act(async () => { form?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });

    expect(onCreateClass).toHaveBeenCalledWith("person", "#ef4444");
  });

  it("allows changing an existing shape to another class", () => {
    const onSave = vi.fn();
    act(() => {
      root?.render(<AnnotationView dataset={{ ...dataset, class_count: 2 }} image={image} classes={[...classes, personClass]} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={onSave} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const classSelect = container?.querySelector<HTMLSelectElement>(".shape-class-select");
    expect(classSelect).toBeTruthy();
    act(() => {
      if (classSelect) classSelect.value = personClass.id;
      classSelect?.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const save = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((button) => button.textContent === "保存标注");
    act(() => save?.click());

    expect(onSave).toHaveBeenCalledWith([{ id: "ann-1", class_id: personClass.id, type: "obb", obb: { cx: 45, cy: 35, width: 30, height: 20, angle: 20 }, source: "manual" }]);
  });

  it("renders a delete button per image and fires onDeleteImage without selecting", () => {
    const onDeleteImage = vi.fn();
    const onImageSelect = vi.fn();
    act(() => {
      root?.render(<AnnotationView dataset={dataset} image={image} images={[image, secondImage]} onImageSelect={onImageSelect} onDeleteImage={onDeleteImage} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const deleteButtons = container?.querySelectorAll<HTMLButtonElement>(".annotation-image-delete") ?? [];
    expect(deleteButtons).toHaveLength(2);

    const target = Array.from(deleteButtons).find((button) => button.getAttribute("aria-label")?.includes(secondImage.file_name));
    expect(target).toBeTruthy();
    act(() => target?.click());

    expect(onDeleteImage).toHaveBeenCalledWith(secondImage);
    expect(onImageSelect).not.toHaveBeenCalled();
  });

  it("does not render delete buttons when no onDeleteImage is provided", () => {
    act(() => {
      root?.render(<AnnotationView dataset={dataset} image={image} images={[image, secondImage]} onImageSelect={vi.fn()} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    expect(container?.querySelectorAll(".annotation-image-delete")).toHaveLength(0);
  });

  it("bulk-deletes selected images", () => {
    const onDeleteImages = vi.fn();
    const third = { ...secondImage, id: "img-3", file_name: "vehicle-03.png" };
    act(() => {
      root?.render(<AnnotationView dataset={{ ...dataset, image_count: 3 }} image={image} images={[image, secondImage, third]} onImageSelect={vi.fn()} onDeleteImages={onDeleteImages} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const toggle = Array.from(container?.querySelectorAll<HTMLButtonElement>(".annotation-bulk-toggle") ?? []).find((button) => button.textContent === "批量操作");
    expect(toggle).toBeTruthy();
    act(() => toggle?.click());

    const selectButtons = Array.from(container?.querySelectorAll<HTMLButtonElement>(".annotation-image-select") ?? []);
    const target1 = selectButtons.find((button) => button.getAttribute("aria-label")?.includes("vehicle-02.png"));
    const target2 = selectButtons.find((button) => button.getAttribute("aria-label")?.includes("vehicle-03.png"));
    act(() => {
      target1?.click();
      target2?.click();
    });

    const confirm = Array.from(container?.querySelectorAll<HTMLButtonElement>("button") ?? []).find((button) => button.textContent === "删除所选");
    expect(confirm).toBeTruthy();
    act(() => confirm?.click());

    expect(onDeleteImages).toHaveBeenCalledWith(["img-2", "img-3"]);
  });

  it("bulk-moves selected images to a split", () => {
    const onMoveImages = vi.fn();
    const third = { ...secondImage, id: "img-3", file_name: "vehicle-03.png" };
    act(() => {
      root?.render(<AnnotationView dataset={{ ...dataset, image_count: 3 }} image={image} images={[image, secondImage, third]} onImageSelect={vi.fn()} onDeleteImages={vi.fn()} onMoveImages={onMoveImages} classes={classes} annotations={[annotation]} activeClassId="cls-1" onClassChange={vi.fn()} onBack={vi.fn()} onSave={vi.fn()} onSam={vi.fn()} onSamPoints={vi.fn()} busy={false} />);
    });

    const toggle = Array.from(container?.querySelectorAll<HTMLButtonElement>(".annotation-bulk-toggle") ?? []).find((button) => button.textContent === "批量操作");
    act(() => toggle?.click());

    const selectButtons = Array.from(container?.querySelectorAll<HTMLButtonElement>(".annotation-image-select") ?? []);
    const target1 = selectButtons.find((button) => button.getAttribute("aria-label")?.includes("vehicle-02.png"));
    const target2 = selectButtons.find((button) => button.getAttribute("aria-label")?.includes("vehicle-03.png"));
    act(() => {
      target1?.click();
      target2?.click();
    });

    const move = Array.from(container?.querySelectorAll<HTMLSelectElement>(".annotation-bulk-move select") ?? [])[0];
    expect(move).toBeTruthy();
    act(() => {
      const nativeSet = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
      if (nativeSet && move) nativeSet.call(move, "test");
      move?.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(onMoveImages).toHaveBeenCalledWith(["img-2", "img-3"], "test");
  });
});
